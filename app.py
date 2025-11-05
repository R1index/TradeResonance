# app.py — optimized
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from flask import Flask, request, redirect, url_for, render_template, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text, select, literal, and_, or_
import sqlalchemy as sa
import csv, io
from flask import Response
from urllib.parse import urlparse
from collections import defaultdict

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
    "pool_pre_ping": True,
    "pool_recycle": 300,
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
    
        "pending_requests": "Pending requests",
        "request_submitted": "Request submitted for review",
        "approve": "Approve",
        "reject": "Reject",
        "approved": "Approved",
        "rejected": "Rejected",
        "admin_password": "Admin password",
        "need_password_for_action": "Admin password required for this action",
        "cannot_edit": "Cannot edit",
        "saving": "Saving...",
        "submitting": "Submitting...",
        "edit_existing": "Entry already exists. Redirected to edit.",
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
    
        "pending_requests": "Заявки на добавление",
        "request_submitted": "Заявка отправлена на рассмотрение",
        "approve": "Одобрить",
        "reject": "Отклонить",
        "approved": "Одобрено",
        "rejected": "Отклонено",
        "admin_password": "Пароль админа",
        "need_password_for_action": "Для этого действия нужен пароль админа",
        "cannot_edit": "Нельзя изменить",
        "saving": "Сохранение...",
        "submitting": "Отправка...",
        "edit_existing": "Запись уже существует. Перенаправляем на редактирование.",
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

    def updated_or_created(self):
        return self.updated_at or self.created_at

class PendingEntry(db.Model):
    __tablename__ = "pending_entries"
    id = db.Column(db.Integer, primary_key=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    city = db.Column(db.String(120), nullable=False, index=True)
    product = db.Column(db.String(120), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    trend = db.Column(db.String(10), nullable=False)  # "up" | "down"
    percent = db.Column(db.Float, nullable=False, default=0.0)
    is_production_city = db.Column(db.Boolean, nullable=False, default=False)
    submit_ip = db.Column(db.String(64))

def approve_pending(p: "PendingEntry"):
    existing = Entry.query.filter_by(city=p.city, product=p.product).first()
    if existing:
        existing.price = p.price
        existing.trend = p.trend
        existing.percent = p.percent
        existing.is_production_city = existing.is_production_city or p.is_production_city
    else:
        e = Entry(
            city=p.city,
            product=p.product,
            price=p.price,
            trend=p.trend,
            percent=p.percent,
            is_production_city=p.is_production_city
        )
        db.session.add(e)
    db.session.delete(p)
    db.session.commit()
    dedupe_entries()

def dedupe_entries():
    rows = (
        db.session.query(Entry)
        .order_by(Entry.city.asc(), Entry.product.asc(),
                  Entry.updated_at.desc().nullslast(), Entry.created_at.desc())
        .all()
    )
    keep: Dict[Tuple[str, str], Entry] = {}
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
        if DATABASE_URL.startswith("sqlite"):
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_entries_product_updated ON entries (product, updated_at DESC, created_at DESC)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_entries_city_updated ON entries (city, updated_at DESC, created_at DESC)"
            ))
        db.session.commit()
    except Exception as e:
        print(f"Index creation warning: {e}")
        db.session.rollback()

def safe_next(url):
    if not url: 
        return None
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.split(':')[0] != request.host.split(':')[0]:
        return None
    return url

def parse_bool(val: Optional[str]) -> bool:
    if isinstance(val, bool): 
        return val
    if val is None: 
        return False
    return str(val).lower() in {"1","true","on","yes","y","да"}
    
def _redirect_to_edit(entry_id: int, lang: str, *, next_url=None, price=None, percent=None, trend=None):
    params = {"entry_id": entry_id, "lang": lang}
    if next_url:
        params["next"] = next_url
    if price not in (None, ""):
        params["price"] = price
    if percent not in (None, ""):
        params["percent"] = percent
    if trend not in (None, ""):
        params["trend"] = trend
    return redirect(url_for("edit_entry", **params))    

@app.context_processor
def inject_base():
    return {"t": t, "lang": get_lang()}

def latest_entries_subq():
    ts = sa.func.coalesce(Entry.updated_at, Entry.created_at).label("ts")
    rn = sa.func.row_number().over(
        partition_by=(Entry.city, Entry.product),
        order_by=sa.desc(ts)
    ).label("rn")

    base = sa.select(
        Entry.id, Entry.city, Entry.product, Entry.price,
        Entry.trend, Entry.percent, Entry.is_production_city,
        Entry.created_at, Entry.updated_at, ts, rn
    ).subquery()

    cols = [c for c in base.c if c.key != "rn"]
    return sa.select(*cols).where(base.c.rn == 1).subquery()

_dict_cache: Dict[str, Tuple[datetime, List[str]]] = {}
def cached_list(key: str, maker):
    now = datetime.utcnow()
    if key in _dict_cache:
        ts, val = _dict_cache[key]
        if now - ts < timedelta(seconds=60):
            return val
    val = maker()
    _dict_cache[key] = (now, val)
    return val

@app.route("/")
def index():
    lang = get_lang()
    tab = request.args.get("tab", "prices")

    if tab == "prices":
        q_city    = (request.args.get("city") or "").strip()
        q_product = (request.args.get("product") or "").strip()
        q_trend   = (request.args.get("trend") or "").strip()
        q_price_min   = request.args.get("price_min", type=float)
        q_price_max   = request.args.get("price_max", type=float)
        q_percent_min = request.args.get("percent_min", type=float)
        q_percent_max = request.args.get("percent_max", type=float)
        q_prod = (request.args.get("prod") or "any").strip().lower()
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

        cities_list = cached_list("cities", lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()])
        products_list = cached_list("products", lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()])

        return render_template(
            "prices.html",
            entries=entries,
            cities_list=cities_list,
            products_list=products_list,
            q_city=q_city, q_product=q_product, q_trend=q_trend,
            q_price_min=q_price_min, q_price_max=q_price_max,
            q_percent_min=q_percent_min, q_percent_max=q_percent_max,
            q_prod=q_prod, q_sort=q_sort,
        )

    elif tab == "cities":
        pf = (request.args.get("pf") or "any").strip().lower()
        if pf not in ("any", "only_prod", "only_nonprod"):
            pf = "any"

        L = latest_entries_subq()
        q = db.session.query(L).select_from(L)
        if pf == "only_prod":
            q = q.filter(L.c.is_production_city.is_(True))
        elif pf == "only_nonprod":
            q = q.filter(L.c.is_production_city.is_(False))

        rows = q.order_by(L.c.city.asc(), L.c.product.asc()).all()

        by_city: Dict[str, List[sa.engine.Row]] = {}
        for r in rows:
            by_city.setdefault(r.city, []).append(r)
        city_list = [{"city": c, "entries": by_city[c]} for c in sorted(by_city.keys(), key=str.lower)]

        cities_list = cached_list("cities", lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()])
        products_list = cached_list("products", lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()])

        return render_template(
            "cities.html",
            city_list=city_list,
            cities_list=cities_list,
            products_list=products_list,
            pf=pf,
        )

    elif tab == "routes":
        q_product = (request.args.get("product") or "").strip()

        L = latest_entries_subq()

        products_list = cached_list(
            "products_latest",
            lambda: [p for (p,) in db.session.query(L.c.product).distinct().order_by(L.c.product.asc()).all()]
        )

        # CTE для покупок (только production cities)
        buy_cte = db.session.query(
            L.c.product.label("product"),
            L.c.city.label("buy_city"),
            L.c.price.label("buy_price"),
            L.c.id.label("buy_id"),
            L.c.trend.label("buy_trend"),
            L.c.percent.label("buy_percent"),
            L.c.updated_at.label("buy_updated"),
            L.c.created_at.label("buy_created"),
            L.c.is_production_city.label("buy_is_production")
        ).filter(L.c.is_production_city == True).subquery()

        # CTE для продаж (все города)
        sell_cte = db.session.query(
            L.c.product.label("product"),
            L.c.city.label("sell_city"),
            L.c.price.label("sell_price"),
            L.c.id.label("sell_id"),
            L.c.trend.label("sell_trend"),
            L.c.percent.label("sell_percent"),
            L.c.updated_at.label("sell_updated"),
            L.c.created_at.label("sell_created"),
            L.c.is_production_city.label("sell_is_production")
        ).subquery()

        routes_query = (
            db.session.query(
                buy_cte.c.product,
                buy_cte.c.buy_city,
                buy_cte.c.buy_price,
                buy_cte.c.buy_id,
                buy_cte.c.buy_trend,
                buy_cte.c.buy_percent,
                buy_cte.c.buy_updated,
                buy_cte.c.buy_created,
                buy_cte.c.buy_is_production,
                
                sell_cte.c.sell_city,
                sell_cte.c.sell_price,
                sell_cte.c.sell_id,
                sell_cte.c.sell_trend,
                sell_cte.c.sell_percent,
                sell_cte.c.sell_updated,
                sell_cte.c.sell_created,
                sell_cte.c.sell_is_production,
                
                ((sell_cte.c.sell_price - buy_cte.c.buy_price) / buy_cte.c.buy_price * 100).label("spread_percent"),
                (sell_cte.c.sell_price - buy_cte.c.buy_price).label("profit")
            )
            .join(sell_cte, buy_cte.c.product == sell_cte.c.product)
            .filter(buy_cte.c.buy_city != sell_cte.c.sell_city)
            .filter(sell_cte.c.sell_price > buy_cte.c.buy_price)
            .order_by((sell_cte.c.sell_price - buy_cte.c.buy_price).desc())
        )
        
        if q_product:
            routes_query = routes_query.filter(buy_cte.c.product.ilike(f"%{q_product}%"))

        routes_result = routes_query.limit(500).all()

        routes = []
        for r in routes_result:
            buy_updated = r.buy_updated or r.buy_created
            sell_updated = r.sell_updated or r.sell_created
            route_updated = max(buy_updated, sell_updated)
            
            routes.append({
                "product": r.product,
                "buy_city": r.buy_city,
                "buy_price": float(r.buy_price),
                "buy_entry_id": int(r.buy_id),
                "buy_trend": r.buy_trend,
                "buy_percent": float(r.buy_percent) if r.buy_percent is not None else None,
                "buy_updated": buy_updated,
                "buy_is_production": bool(r.buy_is_production),
                
                "sell_city": r.sell_city,
                "sell_price": float(r.sell_price),
                "sell_entry_id": int(r.sell_id),
                "sell_trend": r.sell_trend,
                "sell_percent": float(r.sell_percent) if r.sell_percent is not None else None,
                "sell_updated": sell_updated,
                "sell_is_production": bool(r.sell_is_production),
                
                "spread_percent": float(r.spread_percent),
                "profit": float(r.profit),
                "route_updated": route_updated,
            })

        return render_template("routes.html",
                               routes=routes,
                               products_list=products_list,
                               q_product=q_product)
    
    return redirect(url_for("index", tab="prices", lang=lang))

@app.route("/entries/new", methods=["GET", "POST"])
def new_entry():
    lang = get_lang()
    cities_list = cached_list("cities", lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()])
    products_list = cached_list("products", lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()])

    if request.method == "POST":
        # 1) Дефолтное действие — submit_request (если отправили Enter-ом без нажатия кнопки)
        action = (request.form.get("_action") or "submit_request").strip()

        # 2) При POST берем next из form, а не из args
        next_url = safe_next(request.form.get("next")) or safe_next(request.args.get("next"))

        # --- Админские действия approve/reject ---
        if action in {"approve", "reject"}:
            admin_pass = request.form.get("admin_pass", "")
            if not admin_pass:
                flash(t("required_password"))
                return redirect(url_for("new_entry", lang=lang))
            if admin_pass != ADMIN_PASSWORD:
                flash(t("wrong_password"))
                return redirect(url_for("new_entry", lang=lang))

            pid = request.form.get("pending_id", type=int)
            if not pid:
                flash(t("no_data"))
                return redirect(url_for("new_entry", lang=lang))

            p = PendingEntry.query.get(pid)
            if not p:
                flash(t("no_data"))
                return redirect(url_for("new_entry", lang=lang))

            if action == "approve":
                approve_pending(p)
                flash(t("approved"))
            else:
                db.session.delete(p)
                db.session.commit()
                flash(t("rejected"))

            return redirect(url_for("new_entry", lang=lang))

        # --- Создание / поиск существующей записи ---
        city = (request.form.get("city") or "").strip()
        product = (request.form.get("product") or "").strip()
        try:
            price = float(request.form.get("price") or 0)
        except:
            price = 0.0
        trend_v = (request.form.get("trend") or "up").strip()
        try:
            percent_v = float(request.form.get("percent") or 0)
        except:
            percent_v = 0.0
        is_prod = parse_bool(request.form.get("is_production_city"))

        if not city or not product:
            flash(t("no_data"))
        else:
            from sqlalchemy import func
            existing_entry = Entry.query.filter(
                func.lower(Entry.city) == func.lower(city),
                func.lower(Entry.product) == func.lower(product)
            ).first()

            # find_existing → редиректим в edit, если нашли
            if action == "find_existing" and existing_entry:
                flash(t("edit_existing"))
                return redirect(url_for(
                    "edit_entry",
                    entry_id=existing_entry.id,
                    lang=lang,
                    next=next_url,
                    price=price or None,
                    percent=percent_v or None,
                    trend=trend_v or None
                ))

            # submit_request → если запись есть, тоже редиректим в edit
            if action == "submit_request" and existing_entry:
                flash(t("edit_existing"))
                return redirect(url_for(
                    "edit_entry",
                    entry_id=existing_entry.id,
                    lang=lang,
                    next=next_url,
                    price=price or None,
                    percent=percent_v or None,
                    trend=trend_v or None
                ))

            # submit_request → записи нет → создаём pending
            if action == "submit_request":
                if price <= 0:
                    flash(t("no_data"))
                else:
                    p = PendingEntry(
                        city=city, product=product, price=price,
                        trend=trend_v, percent=percent_v,
                        is_production_city=is_prod, submit_ip=request.remote_addr
                    )
                    db.session.add(p)
                    db.session.commit()
                    flash(t("request_submitted"))

    pending = PendingEntry.query.order_by(PendingEntry.submitted_at.desc()).all()
    return render_template("entry_form.html", e=None, title=t("new_entry"),
                           cities_list=cities_list, products_list=products_list,
                           pending=pending, next_url=request.args.get('next'))

@app.route("/entries/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_entry(entry_id):
    lang = get_lang()
    e = Entry.query.get_or_404(entry_id)

    if request.method == "POST":
        try:
            e.price = float(request.form.get("price", e.price))
        except:
            pass
        e.trend = (request.form.get("trend") or e.trend).strip()
        try:
            e.percent = float(request.form.get("percent", e.percent))
        except:
            pass
        db.session.commit()
        flash(t("updated"))
        dedupe_entries()
        next_url = request.form.get("next") or url_for("index", lang=lang)
        return redirect(next_url)

    # значения, пришедшие из /entries/new (для автоподстановки)
    overrides = {
        "price": request.args.get("price") if request.args.get("price") is not None else None,
        "percent": request.args.get("percent") if request.args.get("percent") is not None else None,
        "trend": request.args.get("trend") if request.args.get("trend") is not None else None,
    }

    cities_list = cached_list("cities", lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()])
    products_list = cached_list("products", lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()])
    next_url = safe_next(request.args.get("next")) or safe_next(request.referrer)

    return render_template("entry_form.html", e=e, title=t("edit_entry"),
                           cities_list=cities_list, products_list=products_list,
                           next_url=next_url, overrides=overrides)

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
                    e = Entry(created_at=created_at, city=city, product=product, price=price,
                              trend=trend_v, percent=percent_v, is_production_city=is_prod)
                    db.session.add(e)
                count += 1
            except Exception as ex:
                print(f"Import error: {ex}")
                db.session.rollback()
        db.session.commit()
        dedupe_entries()
        flash(t("imported").format(n=count))
        next_url = request.form.get('next') or url_for('index', lang=lang)
        return redirect(next_url)
    return render_template("import_form.html")

@app.route("/export.csv")
def export_csv():
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
    if q_trend in ("up","down"): 
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
            e.id, e.created_at.isoformat(),
            (e.updated_at or e.created_at).isoformat(),
            e.city, e.product, f"{e.price:.0f}", e.trend, f"{e.percent:.0f}",
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

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
