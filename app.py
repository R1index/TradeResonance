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
        entries = Entry.query.order_by(Entry.created_at.desc()).limit(500).all()
        return render_template("prices.html", entries=entries, t=t, lang=lang)

    
    if tab == "cities":
        # latest entry per (city, product)
        rows = (
            db.session.query(Entry)
            .order_by(Entry.city.asc(), Entry.product.asc(), Entry.created_at.desc())
            .all()
        )
        latest = {}
        for e in rows:
            key = (e.city, e.product)
            if key not in latest:
                latest[key] = e
        # group by city
        by_city = {}
        for (city, product), e in latest.items():
            by_city.setdefault(city, []).append(e)
        # sort products inside city
        for city in by_city:
            by_city[city].sort(key=lambda x: (x.product.lower(), -x.created_at.timestamp()))
        # build list for template with stable city order
        city_list = [{"city": c, "entries": by_city[c]} for c in sorted(by_city.keys(), key=lambda x: x.lower())]
        return render_template("cities.html", city_list=city_list, t=t, lang=lang)
    # routes
    products = [p for (p,) in db.session.query(Entry.product).distinct().all()]
    routes = []
    for prod in products:
        min_row = (
            Entry.query.filter_by(product=prod)
            .order_by(Entry.price.asc())
            .first()
        )
        max_row = (
            Entry.query.filter_by(product=prod)
            .order_by(Entry.price.desc())
            .first()
        )
        if not min_row or not max_row or max_row.price <= min_row.price:
            continue
        spread = (max_row.price - min_row.price) / min_row.price * 100.0
        routes.append({
            "product": prod,
            "buy_city": min_row.city,
            "buy_price": float(min_row.price),
            "sell_city": max_row.city,
            "sell_price": float(max_row.price),
            "spread_percent": float(spread),
            "profit": float(max_row.price - min_row.price),
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
    return render_template("entry_form.html", e=None, t=t, lang=lang, title=t("new_entry"))


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
    return render_template("entry_form.html", e=e, t=t, lang=lang, title=t("edit_entry"))


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
