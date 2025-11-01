# app.py
# -*- coding: utf-8 -*-
"""
Мини‑приложение (один файл) для сбора пользовательских данных и визуализации трендов:
1) Город  2) Товар  3) Цена  4) Тренд  5) Процент
+ автодополнение городов/товаров, EN/RU локализация, график тренда (Chart.js).

Стек: Flask + SQLite + HTMX + Chart.js (CDN) + Datalist typeahead.
Запуск:
    pip install flask python-dateutil
    python app.py
Переменные:
    FLASK_ENV=development (по желанию)
"""
from __future__ import annotations
import csv
import io
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any

from flask import (
    Flask, request, redirect, url_for, jsonify, make_response,
    render_template_string, abort
)

APP_TITLE = "Trade Resonance | Profit Routes"
DB_PATH = os.environ.get("APP_DB", "data.sqlite")

app = Flask(__name__)

# ---------------------- i18n ----------------------

STRINGS: Dict[str, Dict[str, str]] = {
    "ru": {
        "title": "Маршруты прибыли",
        "add_record": "Добавить запись",
        "city": "Город",
        "product": "Товар",
        "price": "Цена",
        "trend": "Тренд",
        "percent": "Процент (опц.)",
        "save": "Сохранить",
        "reset": "Очистить",
        "last_entries": "Последние записи",
        "routes_top": "Топ маршрутов по прибыли",
        "when": "Когда",
        "no_data": "Пока нет данных.",
        "no_routes": "Недостаточно данных для расчёта маршрутов.",
        "trend_up": "Рост",
        "trend_down": "Падение",
        "trend_flat": "Без изм.",
        "from_city": "Из города",
        "to_city": "В город",
        "price_from": "Цена (из)",
        "price_to": "Цена (в)",
        "profit": "Профит",
        "profit_pct": "Профит, %",
        "trend_chart": "Диаграмма тренда",
        "choose_pair": "Выберите город и товар",
        "lang_toggle": "EN",
        "export": "Экспорт CSV",
    },
    "en": {
        "title": "Profit Routes",
        "add_record": "Add entry",
        "city": "City",
        "product": "Product",
        "price": "Price",
        "trend": "Trend",
        "percent": "Percent (opt)",
        "save": "Save",
        "reset": "Reset",
        "last_entries": "Latest entries",
        "routes_top": "Top profit routes",
        "when": "When",
        "no_data": "No data yet.",
        "no_routes": "Not enough data to compute routes.",
        "trend_up": "Up",
        "trend_down": "Down",
        "trend_flat": "Flat",
        "from_city": "From city",
        "to_city": "To city",
        "price_from": "Price (from)",
        "price_to": "Price (to)",
        "profit": "Profit",
        "profit_pct": "Profit, %",
        "trend_chart": "Trend chart",
        "choose_pair": "Select city & product",
        "lang_toggle": "RU",
        "export": "Export CSV",
    },
}

def get_lang() -> str:
    lang = (request.args.get("lang") or request.cookies.get("lang") or "ru").lower()
    return "en" if lang.startswith("en") else "ru"

# ---------------------- DB helpers ----------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    product TEXT NOT NULL,
    price REAL NOT NULL CHECK(price >= 0),
    trend TEXT CHECK(trend IN ('up','down','flat')),
    percent REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_city_product ON entries(city, product);
CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
"""

with get_conn() as c:
    c.executescript(SCHEMA_SQL)

# ---------------------- HTML (Jinja2) ----------------------

BASE_HTML = r"""
<!doctype html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }}</title>
  <script src="https://unpkg.com/htmx.org@2.0.3"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root { --bg:#0b0f14; --card:#111827; --muted:#9ca3af; --text:#e5e7eb; --accent:#22c55e; --border:#1f2937; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial; background: var(--bg); color: var(--text); margin: 0; }
    .container{ max-width: 1200px; margin: 0 auto; padding: 24px; }
    .topbar{ display:flex; justify-content: space-between; align-items:center; margin-bottom: 12px; }
    .grid{ display: grid; grid-template-columns: 1.1fr 1fr; gap: 20px; align-items: start; }
    .grid-2{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
    .card{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 16px; box-shadow: 0 4px 16px rgba(0,0,0,.25); }
    h1{ font-size: 22px; margin: 0 0 12px; }
    h2{ font-size: 18px; margin: 0 0 10px; color: var(--muted); }
    label{ display:block; font-size: 13px; color: var(--muted); margin:10px 0 6px; }
    input, select, button { width: 100%; padding: 10px 12px; border-radius: 10px; border:1px solid var(--border); background: #0f172a; color: var(--text); }
    button{ background: linear-gradient(90deg, #22c55e, #10b981); color:#052e16; font-weight: 600; cursor: pointer; border: none; }
    button.secondary{ background: #0f172a; color: var(--text); border:1px solid var(--border); }
    table{ width:100%; border-collapse: collapse; font-size: 14px; }
    th, td{ padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }
    th{ color: var(--muted); font-weight:600; }
    .pill{ padding: 2px 8px; border-radius: 999px; font-size:12px; display:inline-block; }
    .up{ background:#052e16; color:#22c55e; }
    .down{ background:#3f0a0a; color:#ef4444; }
    .flat{ background:#1f2937; color:#9ca3af; }
    .row{ display:flex; gap:10px; }
    .muted{ color:var(--muted); font-size:12px; }
    .right{ text-align:right; }
    .nowrap{ white-space:nowrap; }
    .actions{ display:flex; gap:10px; }
    .spacer{ height: 10px; }
    a.link{ color:#a7f3d0; text-decoration:none; }
  </style>
</head>
<body>
  <div class="container">
    <div class="topbar">
      <h1>{{ title }}</h1>
      <div class="row">
        <a class="link" href="{{ url_for('index', lang=toggle_lang) }}" onclick="document.cookie='lang={{ toggle_lang }};path=/';">{{ t['lang_toggle'] }}</a>
        <span style="width:10px"></span>
        <a class="link" href="{{ url_for('export_csv') }}">{{ t['export'] }}</a>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>{{ t['add_record'] }}</h2>
        <form id="add-form" hx-post="{{ url_for('add_entry', lang=lang) }}" hx-target="#entries, #routes" hx-select="#entries, #routes" hx-swap="outerHTML" hx-trigger="submit">
          <label>{{ t['city'] }}</label>
          <input id="city" name="city" list="cities" placeholder="Berlin" autocomplete="off" required />
          <datalist id="cities">{% for c in cities %}<option value="{{ c }}">{% endfor %}</datalist>

          <label>{{ t['product'] }}</label>
          <input id="product" name="product" list="products" placeholder="Copper" autocomplete="off" required />
          <datalist id="products">{% for p in products %}<option value="{{ p }}">{% endfor %}</datalist>

          <div class="row">
            <div style="flex:1">
              <label>{{ t['price'] }}</label>
              <input name="price" inputmode="decimal" placeholder="0.00" required />
            </div>
            <div style="flex:1">
              <label>{{ t['trend'] }}</label>
              <select name="trend">
                <option value="up">{{ t['trend_up'] }}</option>
                <option value="flat" selected>{{ t['trend_flat'] }}</option>
                <option value="down">{{ t['trend_down'] }}</option>
              </select>
            </div>
            <div style="flex:1">
              <label>{{ t['percent'] }}</label>
              <input name="percent" inputmode="decimal" placeholder="3.5" />
            </div>
          </div>
          <div class="spacer"></div>
          <div class="actions">
            <button type="submit">{{ t['save'] }}</button>
            <button class="secondary" type="reset">{{ t['reset'] }}</button>
          </div>
        </form>
      </div>

      <div class="card" id="routes" hx-swap-oob="true" hx-get="{{ url_for('routes_view', lang=lang) }}" hx-trigger="load, every 30s" hx-swap="outerHTML"></div>
    </div>

    <div class="grid-2">
      <div class="card" id="entries" hx-swap-oob="true" hx-get="{{ url_for('entries_table', lang=lang) }}" hx-trigger="load, every 15s" hx-swap="outerHTML"></div>

      <div class="card" id="chart-card">
        <h2>{{ t['trend_chart'] }}</h2>
        <div class="row">
          <input id="chart-city" placeholder="{{ t['city'] }}" list="chart-cities" autocomplete="off" />
          <datalist id="chart-cities"></datalist>
          <input id="chart-product" placeholder="{{ t['product'] }}" list="chart-products" autocomplete="off" />
          <datalist id="chart-products"></datalist>
        </div>
        <div class="spacer"></div>
        <canvas id="trendCanvas" height="140"></canvas>
        <p class="muted" id="chart-hint">{{ t['choose_pair'] }}</p>
      </div>
    </div>
  </div>

<script>
// ---- Typeahead for inputs using /suggest ----
function bindTypeahead(inputId, datalistId, field){
  const inp = document.getElementById(inputId);
  const dl = document.getElementById(datalistId);
  let last = '';
  inp.addEventListener('input', async () => {
    const q = inp.value.trim();
    if(q === last) return; last = q;
    const res = await fetch(`/suggest?field=${encodeURIComponent(field)}&q=${encodeURIComponent(q)}`);
    const arr = await res.json();
    dl.innerHTML = arr.map(v=>`<option value="${v}">`).join('');
  });
}

bindTypeahead('chart-city','chart-cities','city');
bindTypeahead('chart-product','chart-products','product');
bindTypeahead('city','cities','city');
bindTypeahead('product','products','product');

// ---- Trend chart ----
let chart;
async function loadSeries(city, product){
  const params = new URLSearchParams({city, product});
  const res = await fetch(`/series.json?${params.toString()}`);
  if(!res.ok){ return; }
  const data = await res.json();
  const labels = data.map(d=>d.ts.replace('T',' ').slice(0,16));
  const prices = data.map(d=>d.price);
  const perc = data.map(d=>d.percent);
  const ctx = document.getElementById('trendCanvas').getContext('2d');
  document.getElementById('chart-hint').textContent = '';
  if(chart){ chart.destroy(); }
  chart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Price', data: prices, tension: 0.25, pointRadius: 2 },
      { label: 'Percent', data: perc, yAxisID: 'y1', tension: 0.25, pointRadius: 2 }
    ]},
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      scales: { y: { beginAtZero: false }, y1: { position: 'right', beginAtZero: false } }
    }
  });
}

function wireChartSelectors(){
  const c = document.getElementById('chart-city');
  const p = document.getElementById('chart-product');
  function maybe(){ if(c.value && p.value){ loadSeries(c.value, p.value); } }
  c.addEventListener('change', maybe);
  p.addEventListener('change', maybe);
}
wireChartSelectors();
</script>
</body>
</html>
"""

ENTRIES_TABLE = r"""
<div class="card" id="entries" hx-swap-oob="true">
  <h2>{{ t['last_entries'] }}</h2>
  <table>
    <thead>
      <tr>
        <th>{{ t['when'] }}</th>
        <th>{{ t['city'] }}</th>
        <th>{{ t['product'] }}</th>
        <th class="right">{{ t['price'] }}</th>
        <th>{{ t['trend'] }}</th>
        <th class="right">{{ t['percent'] }}</th>
      </tr>
    </thead>
    <tbody>
    {% for e in items %}
      <tr>
        <td class="nowrap">{{ e['created_at'][:19].replace('T',' ') }}</td>
        <td>{{ e['city'] }}</td>
        <td>{{ e['product'] }}</td>
        <td class="right">{{ '%.2f'|format(e['price']) }}</td>
        <td>
          {% set tcode = e['trend'] or 'flat' %}
          <span class="pill {{ tcode }}">{{ { 'up': t['trend_up'], 'down': t['trend_down'], 'flat': t['trend_flat'] }[tcode] }}</span>
        </td>
        <td class="right">{{ ('%.2f%%'|format(e['percent'])) if e['percent'] is not none else '—' }}</td>
      </tr>
    {% else %}
      <tr><td colspan="6" class="muted">{{ t['no_data'] }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
"""

ROUTES_TABLE = r"""
<div class="card" id="routes" hx-swap-oob="true">
  <h2>{{ t['routes_top'] }}</h2>
  <table>
    <thead>
      <tr>
        <th>{{ t['product'] }}</th>
        <th>{{ t['from_city'] }}</th>
        <th>{{ t['to_city'] }}</th>
        <th class="right">{{ t['price_from'] }}</th>
        <th class="right">{{ t['price_to'] }}</th>
        <th class="right">{{ t['profit'] }}</th>
        <th class="right">{{ t['profit_pct'] }}</th>
      </tr>
    </thead>
    <tbody>
      {% for r in routes %}
      <tr>
        <td>{{ r['product'] }}</td>
        <td>{{ r['from_city'] }}</td>
        <td>{{ r['to_city'] }}</td>
        <td class="right">{{ '%.2f'|format(r['from_price']) }}</td>
        <td class="right">{{ '%.2f'|format(r['to_price']) }}</td>
        <td class="right">{{ '%.2f'|format(r['profit_abs']) }}</td>
        <td class="right">{{ '%.2f%%'|format(r['profit_pct']) }}</td>
      </tr>
      {% else %}
      <tr><td colspan="7" class="muted">{{ t['no_routes'] }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
"""

# ---------------------- Queries & logic ----------------------

def distinct_values(field: str, limit: int | None = None) -> List[str]:
    assert field in ("city", "product")
    sql = f"SELECT DISTINCT {field} FROM entries ORDER BY {field} ASC"
    params: tuple[Any, ...]
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    else:
        params = ()
    with get_conn() as c:
        cur = c.execute(sql, params)
        return [row[0] for row in cur.fetchall()]


def latest_prices_view() -> List[sqlite3.Row]:
    sql = r"""
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, product, MAX(datetime(created_at)) AS mx
        FROM entries
        GROUP BY city, product
      ) m
      ON e.city = m.city AND e.product = m.product AND datetime(e.created_at) = m.mx
    )
    SELECT * FROM latest ORDER BY datetime(created_at) DESC LIMIT 250
    """
    with get_conn() as c:
        return c.execute(sql).fetchall()


def compute_routes(limit: int = 25) -> List[Dict[str, Any]]:
    sql = r"""
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, product, MAX(datetime(created_at)) AS mx
        FROM entries
        GROUP BY city, product
      ) m
      ON e.city = m.city AND e.product = m.product AND datetime(e.created_at) = m.mx
    )
    SELECT
      a.product AS product,
      a.city AS from_city,
      b.city AS to_city,
      a.price AS from_price,
      b.price AS to_price,
      (b.price - a.price) AS profit_abs,
      CASE WHEN a.price > 0 THEN (b.price - a.price) * 100.0 / a.price ELSE NULL END AS profit_pct
    FROM latest a
    JOIN latest b
      ON a.product = b.product AND a.city <> b.city
    WHERE b.price > a.price
    ORDER BY profit_pct DESC, profit_abs DESC
    LIMIT ?
    """
    with get_conn() as c:
        rows = c.execute(sql, (limit,)).fetchall()
        return [dict(row) for row in rows]

# ---------------------- Routes ----------------------

@app.get("/")
def index():
    lang = get_lang()
    t = STRINGS[lang]
    toggle_lang = 'en' if lang=='ru' else 'ru'
    # Начальные значения в datalist: по 50 штук
    cities = distinct_values("city", limit=50)
    products = distinct_values("product", limit=50)
    resp = make_response(render_template_string(
        BASE_HTML,
        title=f"Trade Resonance | {t['title']}",
        t=t, lang=lang, toggle_lang=toggle_lang,
        cities=cities, products=products,
    ))
    resp.set_cookie('lang', lang, max_age=60*60*24*365)
    return resp

@app.post("/add")
def add_entry():
    def bad(msg: str):
        return make_response(msg, 400)

    city = (request.form.get("city") or "").strip()
    product = (request.form.get("product") or "").strip()
    price_raw = (request.form.get("price") or "").replace(",", ".").strip()
    trend = (request.form.get("trend") or "flat").strip()
    percent_raw = (request.form.get("percent") or "").replace(",", ".").strip()

    if not city or not product:
        return bad("City & product required")
    try:
        price = float(price_raw)
        if price < 0:
            return bad("Price must be non-negative")
    except ValueError:
        return bad("Invalid price")

    percent = None
    if percent_raw:
        try:
            percent = float(percent_raw)
        except ValueError:
            return bad("Invalid percent")

    if trend not in ("up", "down", "flat"):
        trend = "flat"

    created_at = datetime.utcnow().isoformat()
    with get_conn() as c:
        c.execute(
            "INSERT INTO entries(city, product, price, trend, percent, created_at) VALUES (?,?,?,?,?,?)",
            (city, product, price, trend, percent, created_at),
        )

    lang = get_lang()
    entries_html = render_template_string(ENTRIES_TABLE, items=latest_prices_view(), t=STRINGS[lang])
    routes_html = render_template_string(ROUTES_TABLE, routes=compute_routes(), t=STRINGS[lang])
    return entries_html + routes_html

@app.get("/entries")
def entries_table():
    return render_template_string(ENTRIES_TABLE, items=latest_prices_view(), t=STRINGS[get_lang()])

@app.get("/routes")
def routes_view():
    return render_template_string(ROUTES_TABLE, routes=compute_routes(), t=STRINGS[get_lang()])

@app.get("/suggest")
def suggest():
    field = request.args.get("field")
    q = (request.args.get("q") or "").strip()
    if field not in ("city", "product"):
        abort(400)
    like = f"%{q.lower()}%" if q else None
    sql = f"SELECT DISTINCT {field} FROM entries"
    params: tuple[Any, ...]
    if like:
        sql += f" WHERE LOWER({field}) LIKE ?"
        params = (like,)
    else:
        params = ()
    sql += f" ORDER BY {field} ASC LIMIT 20"
    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()
    return jsonify([row[0] for row in rows])

@app.get("/series.json")
def series_json():
    city = (request.args.get('city') or '').strip()
    product = (request.args.get('product') or '').strip()
    if not city or not product:
        return jsonify([])
    sql = (
        "SELECT created_at AS ts, price, trend, percent FROM entries "
        "WHERE city=? AND product=? ORDER BY datetime(created_at) ASC"
    )
    with get_conn() as c:
        rows = c.execute(sql, (city, product)).fetchall()
        data = [dict(r) for r in rows]
    return jsonify(data)

@app.get("/export.csv")
def export_csv():
    sql = "SELECT * FROM entries ORDER BY datetime(created_at) DESC"
    with get_conn() as c:
        rows = c.execute(sql).fetchall()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "city", "product", "price", "trend", "percent"])
    for r in rows:
        writer.writerow([
            r["id"],
            r["created_at"],
            r["city"],
            r["product"],
            r["price"],
            r["trend"],
            "" if r["percent"] is None else r["percent"],
        ])
    csv_data = buffer.getvalue()
    resp = make_response(csv_data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=entries.csv"
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
