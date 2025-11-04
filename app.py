# app.py
# Trade Helper — Flask + SQLAlchemy + Tailwind (CDN)
# Features: EN/RU, responsive UI, routes, cities accordion, filters,
# trend badges, timestamps, deduplication (one row per city+product), upserts, /admin/dedupe
import os
from datetime import datetime
from typing import Optional, Dict, List
from flask import Flask, request, redirect, url_for, render_template, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
import csv, io
from flask import Response

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "reso2025")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,   # проверяет соединение перед запросом
    "pool_recycle": 300,     # переоткрывает коннект каждые 5 минут
}
db = SQLAlchemy(app)

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
        "password": "Password",
        "wrong_password": "Wrong password",
        "required_password": "Password is required",
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
        "password": "Пароль",
        "wrong_password": "Неверный пароль",
        "required_password": "Требуется пароль",
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
            "updated_at": self.updated_at.isoformat() if self.updated_at else self.created_at.isoformat(),
            "city": self.city,
            "product": self.product,
            "price": self.price,
            "trend": self.trend,
            "percent": self.percent,
            "is_production_city": self.is_production_city,
        }

# --- Deduplication ---
def dedupe_entries():
    """Keep latest per (city, product), merge production flag, delete others."""
    rows = (
        db.session.query(Entry)
        .order_by(Entry.city.asc(), Entry.product.asc(), Entry.updated_at.desc(), Entry.created_at.desc())
        .all()
    )
    keep: Dict[tuple, Entry] = {}
    to_delete: List[int] = []
    for e in rows:
        key = (e.city.strip(), e.product.strip())
        if key not in keep:
            keep[key] = e
        else:
            if e.is_production_city and not keep[key].is_production_city:
                keep[key].is_production_city = True
            to_delete.append(e.id)
    if to_delete:
        Entry.query.filter(Entry.id.in_(to_delete)).delete(synchronize_session=False)
    db.session.commit()

with app.app_context():
    db.create_all()
    dedupe_entries()
    try:
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_entries_city_product ON entries (city, product)"))
        db.session.commit()
    except Exception:
        db.session.rollback()

from urllib.parse import urlparse

def safe_next(url):
    """Check redirect safety (only same host)."""
    if not url:
        return None
    netloc = urlparse(url).netloc
    if netloc and netloc != request.host:
        return None
    return url

def parse_bool(val: Optional[str]) -> bool:
    if isinstance(val, bool): return val
    if val is None: return False
    return str(val).lower() in {"1","true","on","yes","y","да"}

@app.context_processor
def inject_base():
    return {"t": t, "lang": get_lang()}

@app.route("/")
def index():
    lang = get_lang()
    tab = request.args.get("tab", "prices")

    if tab == "prices":
        # ── Фильтры (без дат) ─────────────────────────────────────────────
        q_city    = (request.args.get("city") or "").strip()
        q_product = (request.args.get("product") or "").strip()
        q_trend   = (request.args.get("trend") or "").strip()

        q_price_min   = request.args.get("price_min", type=float)
        q_price_max   = request.args.get("price_max", type=float)
        q_percent_min = request.args.get("percent_min", type=float)
        q_percent_max = request.args.get("percent_max", type=float)

        # Производственный город: any|yes|no
        q_prod = (request.args.get("prod") or "any").strip().lower()

        # Сортировка
        # price_asc|price_desc|percent_asc|percent_desc|updated_asc|updated_desc
        q_sort = (request.args.get("sort") or "updated_desc").strip().lower()

        query = Entry.query
        if q_city:
            query = query.filter(Entry.city.ilike(f"%{q_city}%"))
        if q_product:
            query = query.filter(Entry.product.ilike(f"%{q_product}%"))
        if q_trend in ("up", "down"):
            query = query.filter(Entry.trend == q_trend)

        if q_price_min is not None:
            query = query.filter(Entry.price >= q_price_min)
        if q_price_max is not None:
            query = query.filter(Entry.price <= q_price_max)
        if q_percent_min is not None:
            query = query.filter(Entry.percent >= q_percent_min)
        if q_percent_max is not None:
            query = query.filter(Entry.percent <= q_percent_max)

        if q_prod == "yes":
            query = query.filter(Entry.is_production_city.is_(True))
        elif q_prod == "no":
            query = query.filter(Entry.is_production_city.is_(False))

        sort_map = {
            "price_asc": Entry.price.asc(),
            "price_desc": Entry.price.desc(),
            "percent_asc": Entry.percent.asc(),
            "percent_desc": Entry.percent.desc(),
            "updated_asc": Entry.updated_at.asc().nullslast(),
            "updated_desc": Entry.updated_at.desc().nullslast(),
        }
        query = query.order_by(sort_map.get(q_sort, sort_map["updated_desc"]))

        entries = query.limit(1000).all()

        cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
        products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]

        return render_template(
            "prices.html",
            entries=entries,
            cities_list=cities_list,
            products_list=products_list,
            # текущие значения фильтров
            q_city=q_city, q_product=q_product, q_trend=q_trend,
            q_price_min=q_price_min, q_price_max=q_price_max,
            q_percent_min=q_percent_min, q_percent_max=q_percent_max,
            q_prod=q_prod, q_sort=q_sort,
        )

    if tab == "cities":
        # Переключатель: any | only_prod | only_nonprod
        pf = (request.args.get("pf") or "any").strip().lower()
        if pf not in ("any", "only_prod", "only_nonprod"):
            pf = "any"
    
        # Берём только последние записи по (city, product)
        rows = (
            db.session.query(Entry)
            .order_by(Entry.city.asc(), Entry.product.asc(),
                      Entry.created_at.desc())
            .all()
        )
        latest: dict[tuple[str, str], Entry] = {}
        for e in rows:
            key = (e.city, e.product)
            if key not in latest:
                latest[key] = e
    
        # Группируем по городу и применяем фильтр производственности
        by_city: Dict[str, List[Entry]] = {}
        for (city, product), e in latest.items():
            if pf == "only_prod" and not e.is_production_city:
                continue
            if pf == "only_nonprod" and e.is_production_city:
                continue
            by_city.setdefault(city, []).append(e)
    
        # Сортировка внутри города по имени товара (и свежести как tie-breaker)
        for city in by_city:
            by_city[city].sort(key=lambda x: (x.product.lower(), -x.created_at.timestamp()))
    
        # Список городов (только те, где после фильтра есть товары)
        city_list = [
            {"city": c, "entries": by_city[c]}
            for c in sorted([c for c in by_city.keys()], key=lambda x: x.lower())
            if by_city[c]
        ]
    
        # для автодополнений, если нужно где-то в шаблоне
        cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
        products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]
    
        return render_template(
            "cities.html",
            city_list=city_list,
            cities_list=cities_list,
            products_list=products_list,
            pf=pf,  # <<< передаём выбранный режим
        )

    # routes (latest per city for product; buy!=sell city)
    products = [p for (p,) in db.session.query(Entry.product).distinct().all()]
    routes = []
    for prod in products:
        rows = (
            db.session.query(Entry)
            .filter(Entry.product == prod)
            .order_by(Entry.city.asc(), Entry.created_at.desc())
            .all()
        )
        latest_per_city = {}
        for e in rows:
            if e.city not in latest_per_city:
                latest_per_city[e.city] = e
        if len(latest_per_city) < 2:
            continue
        items = list(latest_per_city.items())
        buy_city, buy_entry = min(items, key=lambda kv: kv[1].price)
        sell_city, sell_entry = max(items, key=lambda kv: kv[1].price)
        if sell_entry.price <= buy_entry.price or buy_city == sell_city:
            continue

        spread = (sell_entry.price - buy_entry.price) / buy_entry.price * 100.0
        route_updated = max(
            (buy_entry.updated_at or buy_entry.created_at),
            (sell_entry.updated_at or sell_entry.created_at),
        )

        routes.append({
            "product": prod,
            "buy_city": buy_city,
            "buy_price": float(buy_entry.price),
            "buy_entry_id": buy_entry.id,
            "buy_updated": buy_entry.updated_at or buy_entry.created_at,

            "sell_city": sell_city,
            "sell_price": float(sell_entry.price),
            "sell_entry_id": sell_entry.id,
            "sell_updated": sell_entry.updated_at or sell_entry.created_at,

            "spread_percent": float(spread),
            "profit": float(sell_entry.price - buy_entry.price),
            "route_updated": route_updated,
        })
    routes.sort(key=lambda r: r["profit"], reverse=True)
    return render_template("routes.html", routes=routes)

@app.route("/entries/new", methods=["GET", "POST"])
def new_entry():
    lang = get_lang()
    if request.method == "POST":
        admin_pass = request.form.get("admin_pass", "")
        if not admin_pass:
            flash(t("required_password"))
            return redirect(url_for("new_entry", lang=lang))
        if admin_pass != ADMIN_PASSWORD:
            flash(t("wrong_password"))
            return redirect(url_for("new_entry", lang=lang))
        city = request.form.get("city", "").strip()
        product = request.form.get("product", "").strip()
        price = float(request.form.get("price"))
        trend_v = (request.form.get("trend") or "up").strip()
        percent_v = float(request.form.get("percent") or 0)
        is_prod = parse_bool(request.form.get("is_production_city"))
        existing = Entry.query.filter_by(city=city, product=product).first()
        if existing:
            existing.price = price
            existing.trend = trend_v
            existing.percent = percent_v
            existing.is_production_city = existing.is_production_city or is_prod
            db.session.commit()
            flash(t("updated"))
        else:
            e = Entry(city=city, product=product, price=price, trend=trend_v, percent=percent_v, is_production_city=is_prod)
            db.session.add(e)
            db.session.commit()
            flash(t("saved"))
        dedupe_entries()
        next_url = request.form.get('next') or url_for('index', lang=lang)
        return redirect(next_url)
    cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
    products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]
    # учитываем ?next=... если пришёл (например, из routes)
    next_url = safe_next(request.args.get("next")) or safe_next(request.referrer)
    return render_template('entry_form.html', e=None, title=t('new_entry'),
                           cities_list=cities_list, products_list=products_list, next_url=next_url)

@app.route("/entries/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_entry(entry_id):
    lang = get_lang()
    e = Entry.query.get_or_404(entry_id)
    if request.method == "POST":
        # Разрешаем менять только эти поля
        try:
            e.price = float(request.form.get("price", e.price))
        except Exception:
            pass

        e.trend = (request.form.get("trend") or e.trend).strip()

        try:
            e.percent = float(request.form.get("percent", e.percent))
        except Exception:
            pass

        # 🔒 Не менять флаг при редактировании (в форме у чекбокса нет name)
        if "is_production_city" in request.form:
            e.is_production_city = bool(request.form.get("is_production_city"))

        db.session.commit()
        flash(t("updated"))
        dedupe_entries()
        next_url = request.form.get("next") or url_for("index", lang=lang)
        return redirect(next_url)

    cities_list = [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()]
    products_list = [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()]
    # учитываем ?next=... если пришёл (например, из routes)
    next_url = safe_next(request.args.get("next")) or safe_next(request.referrer)
    return render_template('entry_form.html', e=e, title=t('edit_entry'),
                           cities_list=cities_list, products_list=products_list, next_url=next_url)

@app.route("/import", methods=["GET", "POST"])
def import_csv():
    lang = get_lang()
    if request.method == "POST":
        admin_pass = request.form.get("admin_pass", "")
        if not admin_pass:
            flash(t("required_password"))
            return redirect(url_for("import_csv", lang=lang))
        if admin_pass != ADMIN_PASSWORD:
            flash(t("wrong_password"))
            return redirect(url_for("import_csv", lang=lang))
        file = request.files.get("file")
        if not file:
            flash("No file provided")
            return redirect(url_for("import_csv", lang=lang))
        import csv
        from io import StringIO
        textbuf = file.read().decode("utf-8")
        reader = csv.DictReader(StringIO(textbuf))
        count = 0
        for row in reader:
            try:
                created_at = row.get("created_at")
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else datetime.utcnow()
                city = row.get("city", "").strip()
                product = row.get("product", "").strip()
                price = float(row.get("price"))
                trend_v = (row.get("trend") or "up").strip()
                percent_v = float(row.get("percent") or 0)
                is_prod = parse_bool(row.get("is_production_city"))
                existing = Entry.query.filter_by(city=city, product=product).first()
                if existing:
                    existing.price = price
                    existing.trend = trend_v
                    existing.percent = percent_v
                    existing.is_production_city = existing.is_production_city or is_prod
                    existing.created_at = existing.created_at or created_at
                else:
                    e = Entry(created_at=created_at, city=city, product=product, price=price, trend=trend_v, percent=percent_v, is_production_city=is_prod)
                    db.session.add(e)
                count += 1
            except Exception:
                db.session.rollback()
        db.session.commit()
        dedupe_entries()
        flash(t("imported").format(n=count))
        next_url = request.form.get('next') or url_for('index', lang=lang)
        return redirect(next_url)
    return render_template("import_form.html")

@app.route("/export.csv")
def export_csv():
    # (экспорт можно оставить как есть, он не влияет на Routes)
    q_city = (request.args.get("city") or "").strip()
    q_product = (request.args.get("product") or "").strip()
    q_trend = (request.args.get("trend") or "").strip()
    q_from = (request.args.get("from") or "").strip()
    q_to = (request.args.get("to") or "").strip()

    query = Entry.query
    if q_city:
        query = query.filter(Entry.city.ilike(f"%{q_city}%"))
    if q_product:
        query = query.filter(Entry.product.ilike(f"%{q_product}%"))
    if q_trend in ("up", "down"):
        query = query.filter(Entry.trend == q_trend)

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

    rows = query.order_by(Entry.created_at.desc()).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id","created_at","updated_at","city","product","price","trend","percent","is_production_city"])
    for e in rows:
        w.writerow([
            e.id,
            e.created_at.isoformat(),
            (e.updated_at or e.created_at).isoformat(),
            e.city,
            e.product,
            f"{e.price:.0f}",
            e.trend,
            f"{e.percent:.0f}",
            "true" if e.is_production_city else "false"
        ])

    resp = Response(buf.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = "attachment; filename=entries.csv"
    return resp

@app.route("/admin/dedupe")
def admin_dedupe():
    dedupe_entries()
    flash("Deduplicated")
    return redirect(url_for("index", lang=get_lang()))

@app.route("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
