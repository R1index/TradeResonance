
import os
from datetime import datetime
from urllib.parse import urlencode

from flask import Flask, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Config: DATABASE_URL for Railway, fallback to sqlite for local dev
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    # SQLAlchemy requires postgresql://
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)

# --- Models ---
class Entry(db.Model):
    __tablename__ = "entries"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    city = db.Column(db.String(120), nullable=False)
    product = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, default=0.0)
    percent = db.Column(db.Float, default=0.0)
    trend = db.Column(db.String(10), default="up")
    is_production_city = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('city', 'product', name='uq_city_product'),
    )

class EntryRequest(db.Model):
    __tablename__ = "entry_requests"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    city = db.Column(db.String(120), nullable=False)
    product = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, default=0.0)
    percent = db.Column(db.Float, default=0.0)
    trend = db.Column(db.String(10), default="up")
    status = db.Column(db.String(20), default="pending")  # pending/approved/rejected

# --- i18n helpers (very light) ---
def get_lang():
    lang = (request.args.get("lang") or request.form.get("lang") or "en").lower()
    return "ru" if lang.startswith("ru") else "en"

STRINGS = {
    "en": {
        "title": "TradeResonance",
        "add_entry": "Add Entry",
        "edit_entry": "Edit Entry",
        "city": "City",
        "product": "Product",
        "price": "Price",
        "percent": "Percent",
        "trend": "Trend",
        "trend_up": "Up",
        "trend_down": "Down",
        "trend_flat": "Flat",
        "submit": "Submit",
        "save": "Save",
        "filters": "Filters",
        "nav_routes": "Routes",
        "request_submitted": "Request submitted for review",
        "entry_saved": "Entry saved",
        "back": "Back",
        "clear": "Clear",
        "entries": "Entries",
        "new": "New",
    },
    "ru": {
        "title": "TradeResonance",
        "add_entry": "Добавить запись",
        "edit_entry": "Редактировать запись",
        "city": "Город",
        "product": "Товар",
        "price": "Цена",
        "percent": "Процент",
        "trend": "Тренд",
        "trend_up": "Рост",
        "trend_down": "Падение",
        "trend_flat": "Без изменений",
        "submit": "Отправить",
        "save": "Сохранить",
        "filters": "Фильтры",
        "nav_routes": "Маршруты",
        "request_submitted": "Заявка отправлена на модерацию",
        "entry_saved": "Запись сохранена",
        "back": "Назад",
        "clear": "Очистить",
        "entries": "Записи",
        "new": "Новая",
    },
}

def t(key):
    return STRINGS[get_lang()].get(key, key)

# Cache helpers (very simple in-memory cache per-process)
_cache = {}
def cached_list(key, builder):
    if key not in _cache:
        _cache[key] = builder()
    return _cache[key]

# --- Startup: create tables & dedupe any duplicates (defensive) ---
@app.before_first_request
def init_db_and_dedupe():
    db.create_all()
    # remove duplicates by (city, product) if they somehow exist
    seen = set()
    duplicates = []
    for e in Entry.query.order_by(Entry.id.asc()).all():
        k = (e.city.strip().lower(), e.product.strip().lower())
        if k in seen:
            duplicates.append(e)
        else:
            seen.add(k)
    if duplicates:
        for e in duplicates:
            db.session.delete(e)
        db.session.commit()

# --- Views ---
@app.route("/")
def index():
    lang = get_lang()
    q = Entry.query.order_by(Entry.city.asc(), Entry.product.asc()).all()
    return render_template("index.html", t=t, lang=lang, items=q)

@app.route("/entries/new", methods=["GET", "POST"])
def new_entry():
    lang = get_lang()

    cities_list = cached_list("cities", lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()])
    products_list = cached_list("products", lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()])

    if request.method == "POST":
        action = (request.form.get("_action") or "").strip()  # "submit_request" expected
        city = (request.form.get("city") or "").strip()
        product = (request.form.get("product") or "").strip()

        def f2(x, default=0.0):
            try:
                return float(x)
            except Exception:
                return default

        price = f2(request.form.get("price"))
        percent = f2(request.form.get("percent"))
        trend = (request.form.get("trend") or "up").strip().lower()

        # When record exists -> redirect to edit and pass proposed values
        existing = Entry.query.filter_by(city=city, product=product).first()
        if existing:
            q = {"lang": lang, "price": price, "percent": percent, "trend": trend}
            return redirect(url_for("edit_entry", entry_id=existing.id) + "?" + urlencode(q))

        # Otherwise: create a review request when action matches
        if action == "submit_request":
            req = EntryRequest(city=city, product=product, price=price, percent=percent, trend=trend, status="pending")
            db.session.add(req)
            db.session.commit()
            flash(t("request_submitted"))
            next_url = request.form.get("next") or url_for("index", lang=lang)
            return redirect(next_url)

        # Fallback: create immediate entry (only if needed)
        e = Entry(city=city, product=product, price=price, percent=percent, trend=trend)
        db.session.add(e)
        db.session.commit()
        return redirect(url_for("edit_entry", entry_id=e.id, lang=lang))

    # GET
    next_url = request.args.get("next") or request.referrer or url_for("index", lang=lang)
    return render_template(
        "entries/new.html",
        t=t, lang=lang, next_url=next_url,
        cities_list=cities_list, products_list=products_list
    )

@app.route("/entries/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_entry(entry_id):
    lang = get_lang()
    e = Entry.query.get_or_404(entry_id)

    if request.method == "POST":
        def f2(x, default=0.0):
            try:
                return float(x)
            except Exception:
                return default

        e.price = f2(request.form.get("price"), e.price)
        e.percent = f2(request.form.get("percent"), e.percent)
        e.trend = (request.form.get("trend") or e.trend or "up").strip().lower()
        e.is_production_city = bool(request.form.get("is_production_city"))
        db.session.commit()
        flash(t("entry_saved"))
        next_url = request.form.get("next") or url_for("index", lang=lang)
        return redirect(next_url)

    # GET with pre-populated values from query params (do not save yet)
    pre_price = request.args.get("price", type=float)
    pre_percent = request.args.get("percent", type=float)
    pre_trend = request.args.get("trend")

    next_url = request.args.get("next") or request.referrer or url_for("index", lang=lang)

    return render_template(
        "entries/edit.html",
        t=t, lang=lang, e=e,
        pre_price=pre_price, pre_percent=pre_percent, pre_trend=pre_trend,
        next_url=next_url
    )

# Run locally
if __name__ == "__main__":
    app.run(debug=True, port=5000)
