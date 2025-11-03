# app.py
# Simple Trade Helper for Resonance Solstice — Flask + SQLAlchemy
# Deployable on Railway with PostgreSQL (uses DATABASE_URL)

import os
from datetime import datetime
from typing import Optional, Dict, List

from flask import (
    Flask, request, redirect, url_for, render_template,
    flash, session
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# -----------------------
# Configuration
# -----------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy expects postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------
# I18N (EN/RU) — minimal
# -----------------------
STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "app_title": "Trade Helper",
        "nav_prices": "Prices",
        "nav_cities": "Cities",
        "nav_routes": "Profitable Routes",
        "nav_add": "Add Entry",
        "nav_import": "Import CSV",
        "price": "Price",
        "percent": "Percent",
        "trend": "Trend",
        "up": "up",
        "down": "down",
        "city": "City",
        "product": "Product",
        "is_prod_city": "Production city",
        "yes": "Yes",
        "no": "No",
        "actions": "Actions",
        "edit": "Edit",
        "save": "Save",
        "create": "Create",
        "delete": "Delete",
        "new_entry": "New Entry",
        "edit_entry": "Edit Entry",
        "lang": "Language",
        "upload_csv": "Upload CSV",
        "choose_file": "Choose file",
        "import": "Import",
        "growth": "Growth",
        "drop": "Drop",
        "filters": "Filters",
        "route_buy": "Buy in",
        "route_sell": "Sell in",
        "spread": "Spread",
        "profit": "Profit",
        "no_data": "No data yet.",
        "produces": "Produces",
        "avg_price": "Avg price",
        "submit": "Submit",
        "edit_existing": "Edit existing entries",
        "back": "Back",
        "imported": "Imported {n} rows",
        "saved": "Saved",
        "updated": "Updated",
    },
    "ru": {
        "app_title": "Трейд Хелпер",
        "nav_prices": "Цены",
        "nav_cities": "Города",
        "nav_routes": "Маршруты",
        "nav_add": "Добавить запись",
        "nav_import": "Импорт CSV",
        "price": "Цена",
        "percent": "Процент",
        "trend": "Тренд",
        "up": "рост",
        "down": "падение",
        "city": "Город",
        "product": "Товар",
        "is_prod_city": "Производственный город",
        "yes": "Да",
        "no": "Нет",
        "actions": "Действия",
        "edit": "Править",
        "save": "Сохранить",
        "create": "Создать",
        "delete": "Удалить",
        "new_entry": "Новая запись",
        "edit_entry": "Редактировать запись",
        "lang": "Язык",
        "upload_csv": "Загрузить CSV",
        "choose_file": "Выберите файл",
        "import": "Импорт",
        "growth": "Рост",
        "drop": "Падение",
        "filters": "Фильтры",
        "route_buy": "Покупать в",
        "route_sell": "Продавать в",
        "spread": "Спред",
        "profit": "Профит",
        "no_data": "Данных пока нет.",
        "produces": "Производит",
        "avg_price": "Средняя цена",
        "submit": "Отправить",
        "edit_existing": "Редактировать существующие записи",
        "back": "Назад",
        "imported": "Импортировано {n} строк",
        "saved": "Сохранено",
        "updated": "Обновлено",
    }
}


def get_lang() -> str:
    lang = request.args.get("lang") or session.get("lang") or "ru"
    if lang not in ("en", "ru"):
        lang = "en"
    session["lang"] = lang
    return lang


def t(key: str) -> str:
    return STRINGS.get(get_lang(), STRINGS["en"]).get(key, key)


# -----------------------
# DB Model
# -----------------------
class Entry(db.Model):
    __tablename__ = "entries"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    city = db.Column(db.String(120), nullable=False, index=True)
    product = db.Column(db.String(120), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    trend = db.Column(db.String(10), nullable=False)  # "up" | "down"
    percent = db.Column(db.Float, nullable=False, default=0.0)
    is_production_city = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": (self.updated_at.isoformat() if hasattr(self, "updated_at") and self.updated_at else self.created_at.isoformat()),
            "city": self.city,
            "product": self.product,
            "price": self.price,
            "trend": self.trend,
            "percent": self.percent,
            "is_production_city": self.is_production_city,
        }


with app.app_context():
    db.create_all()


# -----------------------
# Helpers
# -----------------------
def parse_bool(val: Optional[str]) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).lower() in {"1", "true", "on", "yes", "y", "да"}


# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    lang = get_lang()
    tab = request.args.get("tab", "prices")

    
    if tab == "prices":
        # Filters
        q_city = request.args.get("city", "").strip()
        q_product = request.args.get("product", "").strip()
        q_trend = request.args.get("trend", "").strip()
        q_from = request.args.get("from", "").strip()
        q_to = request.args.get("to", "").strip()

        query = Entry.query
        if q_city:
            query = query.filter(Entry.city.ilike(f"%{q_city}%"))
        if q_product:
            query = query.filter(Entry.product.ilike(f"%{q_product}%"))
        if q_trend in ("up", "down"):
            query = query.filter(Entry.trend == q_trend)
        # Date filters based on created_at
        def parse_dt(s):
            try:
                return datetime.fromisoformat(s)
            except Exception:
                try:
                    return datetime.fromisoformat(s + "T00:00:00")
                except Exception:
                    return None
        dt_from = parse_dt(q_from) if q_from else None
        dt_to = parse_dt(q_to) if q_to else None
        if dt_from:
            query = query.filter(Entry.created_at >= dt_from)
        if dt_to:
            query = query.filter(Entry.created_at <= dt_to)

        entries = query.order_by(Entry.created_at.desc()).limit(1000).all()

        # Distinct lists for autocomplete
        cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
        products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]

        return render_template("prices.html", entries=entries, t=t, lang=lang,
                               cities_list=cities_list, products_list=products_list,
                               q_city=q_city, q_product=q_product, q_trend=q_trend,
                               q_from=q_from, q_to=q_to)

    
    
    if tab == "cities":
        # use only production-marked entries
        rows = (
            db.session.query(Entry)
            .filter(Entry.is_production_city.is_(True))
            .order_by(Entry.city.asc(), Entry.product.asc(), Entry.created_at.desc())
            .all()
        )
        latest = {}
        for e in rows:
            key = (e.city, e.product)
            if key not in latest:
                latest[key] = e
        by_city = {}
        for (city, product), e in latest.items():
            by_city.setdefault(city, []).append(e)
        for city in by_city:
            by_city[city].sort(key=lambda x: (x.product.lower(), -x.created_at.timestamp()))
        city_list = [{"city": c, "entries": by_city[c]} for c in sorted(by_city.keys(), key=lambda x: x.lower())]
        # Distinct lists for autocomplete in potential future actions
        cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
        products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]
        return render_template("cities.html", city_list=city_list, t=t, lang=lang,
                               cities_list=cities_list, products_list=products_list)
    
    # routes
    # Compute best routes using the LATEST price per (city, product) so buy/sell are from different cities.
    products = [p for (p,) in db.session.query(Entry.product).distinct().all()]
    routes = []
    for prod in products:
        # latest per city for this product
        rows = (
            db.session.query(Entry)
            .filter(Entry.product == prod)
            .order_by(Entry.city.asc(), Entry.created_at.desc())
            .all()
        )
        latest_per_city = {}
        for e in rows:
            if e.city not in latest_per_city:
                latest_per_city[e.city] = e  # keep most recent for that city
        if len(latest_per_city) < 2:
            continue  # need at least two distinct cities
        # get min and max across cities
        items = list(latest_per_city.items())
        buy_city, buy_entry = min(items, key=lambda kv: kv[1].price)
        sell_city, sell_entry = max(items, key=lambda kv: kv[1].price)
        if sell_entry.price <= buy_entry.price or buy_city == sell_city:
            continue
        spread = (sell_entry.price - buy_entry.price) / buy_entry.price * 100.0
        routes.append({
            "product": prod,
            "buy_city": buy_city,
            "buy_price": float(buy_entry.price),
            "sell_city": sell_city,
            "sell_price": float(sell_entry.price),
            "spread_percent": float(spread),
            "profit": float(sell_entry.price - buy_entry.price),
        })
    routes.sort(key=lambda r: r["profit"], reverse=True)
    return render_template("routes.html", routes=routes, t=t, lang=lang)


@app.route("/entries/new", methods=["GET", "POST"])
def new_entry():
    lang = get_lang()
    if request.method == "POST":
        e = Entry(
            city=request.form.get("city", "").strip(),
            product=request.form.get("product", "").strip(),
            price=float(request.form.get("price")),
            trend=(request.form.get("trend") or "up").strip(),
            percent=float(request.form.get("percent") or 0),
            is_production_city=parse_bool(request.form.get("is_production_city")),
        )
        db.session.add(e)
        db.session.commit()
        flash(t("saved"))
        return redirect(url_for("index", lang=lang))
    cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
    products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]
    return render_template("entry_form.html", e=None, t=t, lang=lang, title=t("new_entry"), cities_list=cities_list, products_list=products_list)


@app.route("/entries/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_entry(entry_id):
    lang = get_lang()
    e = Entry.query.get_or_404(entry_id)
    if request.method == "POST":
        e.city = request.form.get("city", e.city).strip()
        e.product = request.form.get("product", e.product).strip()
        e.price = float(request.form.get("price", e.price))
        e.trend = (request.form.get("trend") or e.trend).strip()
        e.percent = float(request.form.get("percent", e.percent))
        e.is_production_city = parse_bool(request.form.get("is_production_city"))
        db.session.commit()
        flash(t("updated"))
        return redirect(url_for("index", lang=lang))
    cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
    products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]
    return render_template("entry_form.html", e=e, t=t, lang=lang, title=t("edit_entry"), cities_list=cities_list, products_list=products_list)


@app.route("/import", methods=["GET", "POST"])
def import_csv():
    lang = get_lang()
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("No file provided")
            return redirect(url_for("import_csv", lang=lang))
        import csv
        from io import StringIO
        text = file.read().decode("utf-8")
        reader = csv.DictReader(StringIO(text))
        count = 0
        for row in reader:
            try:
                created_at = row.get("created_at")
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else datetime.utcnow()
                e = Entry(
                    created_at=created_at,
                    city=row.get("city", "").strip(),
                    product=row.get("product", "").strip(),
                    price=float(row.get("price")),
                    trend=(row.get("trend") or "up").strip(),
                    percent=float(row.get("percent") or 0),
                    is_production_city=parse_bool(row.get("is_production_city")),
                )
                db.session.add(e)
                count += 1
            except Exception:
                db.session.rollback()
        db.session.commit()
        flash(t("imported").format(n=count))
        return redirect(url_for("index", lang=lang))
    return render_template("import_form.html", t=t, lang=lang)


# ---------------
# Healthcheck
# ---------------
@app.route("/health")
def health():
    return {"status": "ok"}


# ---------------
# Template helpers
# ---------------
@app.context_processor
def inject_base():
    return {"t": t, "lang": get_lang()}


# ---------------
# Local run
# ---------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
