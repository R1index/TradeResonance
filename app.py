# app.py
# -*- coding: utf-8 -*-
"""
Мини‑приложение (один файл) для сбора пользовательских данных и визуализации трендов:
1) Город  2) Товар  3) Цена  4) Тренд  5) Процент
+ автодополнение городов/товаров, EN/RU локализация, график тренда (Chart.js).

Стек: Flask + PostgreSQL (Railway) + HTMX + Chart.js (CDN) + Datalist typeahead.
Запуск:
    pip install flask python-dateutil psycopg[binary]
    export DATABASE_URL=postgresql://user:pass@host:port/dbname
    python app.py
Переменные:
    FLASK_ENV=development (по желанию)
"""
from __future__ import annotations
import csv
import io
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Iterable, Mapping

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    make_response,
    render_template_string,
    request,
    url_for,
)

import psycopg
from psycopg.rows import dict_row

APP_TITLE = "Trade Resonance"
DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("RAILWAY_DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
)

ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "reso2025")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL (или совместимая переменная окружения) не задана. "
        "Укажите строку подключения Railway PostgreSQL."
    )

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
        "trend_hint": "Восходящий и нисходящий тренд",
        "percent": "Процент, %",
        "save": "Сохранить",
        "reset": "Очистить",
        "last_entries": "Последние записи",
        "routes_top": "Топ маршрутов по прибыли",
        "production_city": "Производство города",
        "production_city_short": "Производство",
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
        "import": "Импорт CSV",
        "search": "Найти",
        "product_lookup": "Цены по товарам",
        "product_lookup_placeholder": "Введите товар",
        "product_lookup_hint": "Введите название товара и нажмите \"Найти\".",
        "no_prices": "Нет данных по выбранному товару.",
        "prices_for": "Цены для",
        "sort_label": "Сортировать",
        "sort_price_low": "Цена ↑",
        "sort_price_high": "Цена ↓",
        "entries_count": "записей",
        "city_products": "Товары города",
        "city_products_hint": "Выберите город и нажмите \"Найти\".",
        "city_products_no_data": "Нет данных о производстве выбранного города.",
        "city_products_for": "Производство города",
        "password_placeholder": "Пароль доступа",
        "password_hint": "Пароль нужен для сохранения и работы с CSV.",
        "password_required": "Введите пароль доступа",
        "password_invalid": "Неверный пароль",
        "click_to_fill": "Кликните, чтобы подставить запись в форму",
        "latest_autofill_label": "Автоподстановка",
        "latest_autofill_loading": "Ищем последнюю запись...",
        "latest_autofill_missing": "Совпадений пока нет",
        "latest_autofill_from": "Запись от",
        "latest_autofill_auto": "Цена обновлена автоматически",
    },
    "en": {
        "title": "Profit Routes",
        "add_record": "Add entry",
        "city": "City",
        "product": "Product",
        "price": "Price",
        "trend": "Trend",
        "trend_hint": "Upward or downward trend",
        "percent": "Percent, %",
        "save": "Save",
        "reset": "Reset",
        "last_entries": "Latest entries",
        "routes_top": "Top profit routes",
        "production_city": "Production city",
        "production_city_short": "Production",
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
        "import": "Import CSV",
        "search": "Search",
        "product_lookup": "Prices by product",
        "product_lookup_placeholder": "Enter product",
        "product_lookup_hint": "Type a product name and press \"Search\".",
        "no_prices": "No data for the selected product.",
        "prices_for": "Prices for",
        "sort_label": "Sort",
        "sort_price_low": "Price ↑",
        "sort_price_high": "Price ↓",
        "entries_count": "entries",
        "city_products": "City production",
        "city_products_hint": "Choose a city and press \"Search\".",
        "city_products_no_data": "No production data for the selected city.",
        "city_products_for": "City production for",
        "password_placeholder": "Access password",
        "password_hint": "Password is required for saving and CSV actions.",
        "password_required": "Enter the access password",
        "password_invalid": "Invalid password",
        "click_to_fill": "Click to send the row to the form",
        "latest_autofill_label": "Autofill",
        "latest_autofill_loading": "Looking up the last entry...",
        "latest_autofill_missing": "No matching entries yet",
        "latest_autofill_from": "Entry from",
        "latest_autofill_auto": "Price updated automatically",
    },
}

def get_lang() -> str:
    lang = (request.args.get("lang") or request.cookies.get("lang") or "ru").lower()
    return "en" if lang.startswith("en") else "ru"

# ---------------------- DB helpers ----------------------


def get_conn():
    return psycopg.connect(DATABASE_URL, autocommit=False, row_factory=dict_row)


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS entries (
        id SERIAL PRIMARY KEY,
        city TEXT NOT NULL,
        product TEXT NOT NULL,
        price DOUBLE PRECISION NOT NULL CHECK(price >= 0),
        trend TEXT CHECK(trend IN ('up','down','flat')),
        percent DOUBLE PRECISION,
        is_production_city BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_entries_city_product ON entries(city, product)",
    "CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at)",
)


def ensure_schema() -> None:
    with get_conn() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)


ensure_schema()

# ---------------------- utils ----------------------


def password_matches(submitted: str | None) -> bool:
    if ACCESS_PASSWORD:
        return submitted == ACCESS_PASSWORD
    return True


def submitted_password() -> str:
    """Считывает пароль из формы, query string или заголовка."""

    candidates = (
        request.values.get("password"),
        request.headers.get("X-Access-Password"),
    )
    for value in candidates:
        if value:
            return value.strip()
    return ""


def ensure_password(lang: str) -> Response | None:
    """Проверяет пароль и возвращает ответ 403 при ошибке."""

    if not password_matches(submitted_password()):
        return make_response(STRINGS[lang]["password_invalid"], 403)
    return None


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = _as_utc(value).isoformat(timespec="seconds")
    return result


def rows_to_dicts(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [_normalize_row(r) for r in rows]


def render_fragment(template: str, *, lang: str, **context: Any) -> str:
    ctx = dict(context)
    ctx.setdefault("t", STRINGS[lang])
    return render_template_string(template, **ctx)


def render_entries_and_routes(lang: str) -> str:
    entries_html = render_fragment(ENTRIES_TABLE, lang=lang, items=latest_prices_view())
    routes_html = render_fragment(ROUTES_TABLE, lang=lang, routes=compute_routes())
    return entries_html + routes_html

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
    :root {
      --bg: #06090f;
      --bg-gradient: radial-gradient(circle at 20% 20%, rgba(34,197,94,0.12), transparent 55%),
        radial-gradient(circle at 80% 0%, rgba(59,130,246,0.12), transparent 40%),
        #06090f;
      --card: rgba(15, 23, 42, 0.92);
      --muted: #9ca3af;
      --text: #e5e7eb;
      --accent: #22c55e;
      --border: rgba(148, 163, 184, 0.18);
      --border-strong: rgba(148, 163, 184, 0.32);
    }
    body {
      font-family: "Inter", system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Noto Sans", Helvetica, Arial;
      background: var(--bg-gradient);
      color: var(--text);
      margin: 0;
    }
    * {
      box-sizing: border-box;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }
    .app-header {
      display: flex;
      align-items: center;
      gap: 20px;
      justify-content: space-between;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 14px;
    }
    .brand-logo {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      background: linear-gradient(140deg, rgba(34,197,94,0.9), rgba(59,130,246,0.85));
      color: #041f0f;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 16px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      box-shadow: 0 12px 24px rgba(34, 197, 94, 0.28);
    }
    .brand-text {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .brand-title {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.01em;
    }
    .brand-subtitle {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.2em;
      color: var(--muted);
    }
    .nav-toggle {
      display: none;
      width: 46px;
      height: 46px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(8, 13, 23, 0.85);
      color: var(--text);
      align-items: center;
      justify-content: center;
      cursor: pointer;
      padding: 0;
      transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
      min-height: 0;
    }
    .nav-toggle:hover {
      background: rgba(15, 23, 42, 0.95);
      border-color: rgba(34, 197, 94, 0.35);
      transform: none;
      box-shadow: 0 12px 28px rgba(8, 13, 23, 0.45);
    }
    .nav-toggle:focus-visible {
      outline: none;
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.35);
      border-color: rgba(34, 197, 94, 0.5);
    }
    .nav-toggle-bar {
      position: relative;
      width: 20px;
      height: 2px;
      border-radius: 999px;
      background: var(--text);
      transition: transform 0.2s ease, background 0.2s ease;
    }
    .nav-toggle-bar::before,
    .nav-toggle-bar::after {
      content: "";
      position: absolute;
      left: 0;
      width: 20px;
      height: 2px;
      border-radius: 999px;
      background: var(--text);
      transition: transform 0.2s ease;
    }
    .nav-toggle-bar::before {
      transform: translateY(-6px);
    }
    .nav-toggle-bar::after {
      transform: translateY(6px);
    }
    .nav-toggle[aria-expanded="true"] .nav-toggle-bar {
      background: transparent;
    }
    .nav-toggle[aria-expanded="true"] .nav-toggle-bar::before {
      transform: rotate(45deg);
    }
    .nav-toggle[aria-expanded="true"] .nav-toggle-bar::after {
      transform: rotate(-45deg);
    }
    .nav-menu {
      display: flex;
      align-items: center;
      gap: 18px;
      margin-left: auto;
    }
    .nav-section {
      display: inline-flex;
      align-items: center;
      gap: 12px;
    }
    .nav-actions {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .nav-actions form {
      margin: 0;
    }
    .nav-clock {
      margin-left: auto;
    }
    .nav-divider {
      width: 1px;
      height: 32px;
      background: var(--border);
      opacity: 0.75;
    }
    .clock-display {
      font-family: "JetBrains Mono", "Roboto Mono", "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 14px;
      letter-spacing: 0.08em;
      color: var(--muted);
      padding: 8px 16px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(8, 13, 23, 0.78);
      font-variant-numeric: tabular-nums;
      min-width: 140px;
      text-align: center;
      box-shadow: inset 0 0 0 1px rgba(34, 197, 94, 0.14);
    }
    .clock-display[data-timezone]::after {
      content: attr(data-timezone);
      display: block;
      font-size: 11px;
      letter-spacing: 0.12em;
      margin-top: 4px;
      color: var(--muted);
      opacity: 0.75;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
    }
    .tab-button {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid var(--border);
      color: var(--muted);
      padding: 10px 16px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
    }
    .tab-button.active {
      background: rgba(34, 197, 94, 0.18);
      border-color: rgba(34, 197, 94, 0.45);
      color: var(--text);
    }
    .tab-button:focus-visible {
      outline: none;
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.35);
    }
    .tab-panels {
      display: grid;
      gap: 20px;
    }
    .tab-panel {
      display: none;
    }
    .tab-panel.active {
      display: block;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 20px 40px rgba(15, 23, 42, 0.3);
      backdrop-filter: blur(12px);
    }
    h1 {
      font-size: 24px;
      margin: 0 0 12px;
    }
    h2 {
      font-size: 18px;
      margin: 0;
      color: var(--muted);
      font-weight: 600;
    }
    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin: 10px 0 6px;
      font-weight: 600;
      letter-spacing: 0.01em;
    }
    input,
    select,
    button {
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: rgba(8, 13, 23, 0.9);
      color: var(--text);
      transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.1s ease;
    }
    input:focus,
    select:focus,
    button:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.25);
    }
    button {
      background: linear-gradient(120deg, #22c55e, #16a34a);
      color: #052e16;
      font-weight: 600;
      cursor: pointer;
      border: none;
      min-height: 44px;
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      box-shadow: none;
      transform: none;
    }
    button.secondary {
      background: rgba(15, 23, 42, 0.85);
      color: var(--text);
      border: 1px solid var(--border-strong);
    }
    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 20px rgba(34, 197, 94, 0.25);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th,
    td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }
    th {
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 0.08em;
    }
    tbody tr:nth-child(even) {
      background: rgba(148, 163, 184, 0.06);
    }
    tbody tr:hover {
      background: rgba(34, 197, 94, 0.08);
    }
    tbody tr.entry-row {
      cursor: pointer;
    }
    .table-scroll {
      margin-top: 14px;
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: auto;
      max-height: 360px;
      background: rgba(8, 13, 23, 0.65);
    }
    .table-scroll table {
      min-width: 560px;
    }
    .pill {
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 12px;
      display: inline-block;
      font-weight: 600;
    }
    .up {
      background: rgba(34, 197, 94, 0.12);
      color: #4ade80;
    }
    .down {
      background: rgba(248, 113, 113, 0.12);
      color: #fca5a5;
    }
    .flat {
      background: rgba(148, 163, 184, 0.12);
      color: #cbd5f5;
    }
    .row {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .row.wrap {
      flex-wrap: wrap;
      gap: 16px;
      align-items: stretch;
    }
    .row.wrap > * {
      flex: 1 1 220px;
    }
    .nav-password {
      align-items: flex-start;
    }
    .nav-password .password-box {
      min-width: 220px;
    }
    .nav-actions button,
    .nav-actions .link-button,
    .nav-actions a.link {
      flex: 0 0 auto;
    }
    .link-button,
    a.link {
      width: auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 18px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(15, 23, 42, 0.88);
      color: #a7f3d0;
      cursor: pointer;
      font-weight: 600;
      letter-spacing: 0.03em;
      font-size: 14px;
      text-decoration: none;
      min-height: 44px;
      transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
    }
    .link-button:hover,
    a.link:hover {
      color: #bbf7d0;
      border-color: rgba(34, 197, 94, 0.45);
      background: rgba(34, 197, 94, 0.16);
      box-shadow: 0 10px 24px rgba(34, 197, 94, 0.18);
    }
    .link-button:focus-visible,
    a.link:focus-visible {
      outline: none;
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.35);
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .muted {
      color: var(--muted);
      font-size: 12px;
    }
    .muted-block {
      color: var(--muted);
      font-size: 13px;
      margin-top: 10px;
    }
    .right {
      text-align: right;
    }
    .nowrap {
      white-space: nowrap;
    }
    .actions {
      display: flex;
      gap: 10px;
      margin-top: 12px;
    }
    .percent-control {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .percent-control input[type="range"] {
      flex: 1 1 140px;
      min-width: 120px;
    }
    .percent-btn {
      width: auto;
      padding: 6px 10px;
      font-size: 12px;
      border-radius: 999px;
      background: rgba(34, 197, 94, 0.18);
      color: #4ade80;
      border: 1px solid rgba(34, 197, 94, 0.4);
      min-height: 36px;
    }
    .percent-btn:hover {
      transform: translateY(-1px);
      box-shadow: none;
      background: rgba(34, 197, 94, 0.28);
    }
    .percent-presets {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }
    .latest-autofill {
      margin-top: 12px;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(15, 22, 35, 0.65);
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }
    .latest-autofill__label {
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
      white-space: nowrap;
      margin-top: 2px;
    }
    .latest-autofill__content {
      font-size: 13px;
      line-height: 1.4;
      color: var(--muted);
    }
    .latest-autofill.success .latest-autofill__content {
      color: #d6ecff;
    }
    .latest-autofill.loading .latest-autofill__content {
      opacity: 0.8;
    }
    @keyframes pulse-highlight {
      0% { box-shadow: 0 0 0 rgba(77, 160, 255, 0.0); }
      30% { box-shadow: 0 0 0 6px rgba(77, 160, 255, 0.15); }
      100% { box-shadow: 0 0 0 rgba(77, 160, 255, 0.0); }
    }
    .pulse-highlight {
      animation: pulse-highlight 1.2s ease;
    }
    .percent-preset {
      width: auto;
      padding: 6px 12px;
      font-size: 12px;
      border-radius: 999px;
      background: rgba(34, 197, 94, 0.12);
      color: #bbf7d0;
      border: 1px solid rgba(34, 197, 94, 0.28);
      cursor: pointer;
      transition: transform 0.15s ease, box-shadow 0.2s ease;
      min-height: 36px;
    }
    .percent-preset:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 18px rgba(34, 197, 94, 0.2);
    }
    .password-box {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 180px;
    }
    .password-hint {
      font-size: 11px;
      color: var(--muted);
    }
    .percent-display {
      min-width: 52px;
      text-align: right;
    }
    .trend-field {
      margin-top: 18px;
    }
    .trend-caption {
      display: block;
      font-size: 13px;
      color: #e2e8f0;
      font-weight: 600;
      letter-spacing: 0.02em;
      margin-bottom: 10px;
    }
    .trend-toggle {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .trend-option {
      position: relative;
      flex: 1 1 140px;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(8, 13, 23, 0.65);
      cursor: pointer;
      transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
    }
    .trend-option:hover {
      border-color: rgba(59, 130, 246, 0.45);
      background: rgba(15, 23, 42, 0.85);
    }
    .trend-option.active.up {
      border-color: rgba(34, 197, 94, 0.8);
      background: rgba(34, 197, 94, 0.12);
      box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.35);
    }
    .trend-option.active.down {
      border-color: rgba(248, 113, 113, 0.85);
      background: rgba(248, 113, 113, 0.12);
      box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.35);
    }
    .trend-option input[type="checkbox"] {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }
    .trend-icon {
      width: 38px;
      height: 38px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: rgba(148, 163, 184, 0.16);
    }
    .trend-option svg {
      width: 22px;
      height: 22px;
    }
    .trend-option.up svg {
      fill: #22c55e;
    }
    .trend-option.down svg {
      fill: #f87171;
    }
    .trend-option .trend-text {
      font-weight: 600;
      color: #e2e8f0;
      letter-spacing: 0.02em;
    }
    .trend-option.active .trend-icon {
      background: rgba(15, 23, 42, 0.95);
    }
    .spacer {
      height: 10px;
    }
    .checkbox {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .checkbox input {
      width: auto;
    }
    .center {
      text-align: center;
    }
    details.collapsible {
      position: relative;
    }
    details.collapsible summary {
      list-style: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    details.collapsible summary::-webkit-details-marker {
      display: none;
    }
    details.collapsible summary h2 {
      flex: 1;
      margin: 0;
    }
    .summary-meta {
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .sort-indicator {
      font-size: 11px;
      color: var(--muted);
      margin-left: 6px;
    }
    .summary-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(8, 13, 23, 0.8);
      transition: transform 0.2s ease;
      font-size: 12px;
    }
    details[open] .summary-icon {
      transform: rotate(180deg);
    }
    /* Responsive navigation: below 900px the header collapses into a stacked drawer
       controlled by the burger button so the layout stays touch-friendly on phones. */
    @media (max-width: 900px) {
      .app-header {
        align-items: flex-start;
      }
      .nav-toggle {
        display: inline-flex;
      }
      .nav-menu {
        display: none;
        flex-direction: column;
        align-items: stretch;
        gap: 18px;
        width: 100%;
        padding: 18px;
        border-radius: 20px;
        border: 1px solid var(--border);
        background: rgba(8, 13, 23, 0.9);
        box-shadow: 0 18px 36px rgba(8, 13, 23, 0.5);
      }
      .nav-menu.open {
        display: flex;
      }
      .nav-section {
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
      }
      .nav-actions {
        flex-direction: column;
        align-items: stretch;
      }
      .nav-actions form,
      .nav-actions a.link,
      .nav-actions .link-button {
        width: 100%;
      }
      .nav-divider {
        width: 100%;
        height: 1px;
        background: rgba(148, 163, 184, 0.25);
      }
      .nav-password .password-box {
        width: 100%;
      }
      .nav-clock {
        margin-left: 0;
      }
      .nav-clock .clock-display {
        width: 100%;
      }
    }
    @media (max-width: 1024px) {
      .container {
        padding: 16px;
      }
      .tab-panels {
        gap: 20px;
      }
      .table-scroll {
        max-height: 420px;
      }
    }
    @media (max-width: 640px) {
      body {
        padding: 10px 0;
      }
      .container {
        padding: 12px;
      }
      h1 {
        font-size: 20px;
      }
      h2 {
        font-size: 16px;
      }
      .app-header {
        gap: 12px;
      }
      .brand-title {
        font-size: 20px;
      }
      .brand-logo {
        width: 40px;
        height: 40px;
      }
      .nav-menu {
        padding: 16px;
        gap: 14px;
      }
      .tabs {
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 16px;
      }
      .tab-button {
        flex: 1 1 150px;
        font-size: 12px;
        padding: 8px 12px;
      }
      .tab-panels {
        gap: 16px;
      }
      .card {
        padding: 16px;
      }
      .row.wrap {
        gap: 12px;
      }
      .row.wrap > * {
        flex: 1 1 160px;
      }
      .tab-panel .row {
        flex-wrap: wrap;
        gap: 12px;
        align-items: stretch;
      }
      .tab-panel .row > * {
        flex: 1 1 100%;
      }
      .actions {
        flex-wrap: wrap;
        gap: 10px;
      }
      .actions button {
        flex: 1 1 160px;
      }
      .percent-control {
        gap: 6px;
      }
      .table-scroll {
        margin-top: 12px;
        border-radius: 12px;
      }
      .table-scroll table {
        min-width: 480px;
      }
      table {
        font-size: 13px;
      }
      th,
      td {
        padding: 8px 10px;
      }
    }
  </style>
</head>
<body>
    <div class="container">
      <header class="app-header">
        <div class="brand">
          <span class="brand-logo" aria-hidden="true">TR</span>
          <div class="brand-text">
            <h1 class="brand-title">{{ app_name or title }}</h1>
            <span class="brand-subtitle">{{ t['title'] }}</span>
          </div>
        </div>
        <button class="nav-toggle" type="button" data-nav-toggle aria-expanded="false" aria-controls="nav-menu">
          <span class="sr-only">Toggle navigation</span>
          <span class="nav-toggle-bar" aria-hidden="true"></span>
        </button>
        <nav class="nav-menu" id="nav-menu" aria-label="Main navigation">
          <div class="nav-section nav-links">
            <a class="link" href="{{ url_for('index', lang=toggle_lang) }}" onclick="document.cookie='lang={{ toggle_lang }};path=/';">{{ t['lang_toggle'] }}</a>
          </div>
          <span class="nav-divider" aria-hidden="true"></span>
          <div class="nav-section nav-password">
            <div class="password-box">
              <input type="password" id="admin-password" placeholder="{{ t['password_placeholder'] }}" autocomplete="off" data-require-message="{{ t['password_required'] }}" />
              <span class="password-hint">{{ t['password_hint'] }}</span>
            </div>
          </div>
          <span class="nav-divider" aria-hidden="true"></span>
          <div class="nav-section nav-actions">
            <form id="import-form" data-require-message="{{ t['password_required'] }}" hx-post="{{ url_for('import_csv_route') }}" hx-target="#entries, #routes" hx-select="#entries, #routes" hx-swap="outerHTML" hx-trigger="change from:#import-file" hx-encoding="multipart/form-data" hx-on::after-request="if(event.detail.successful){ this.reset(); }" hx-on::response-error="alert(event.detail.xhr.responseText || 'Import failed')">
              <input type="hidden" name="password" data-password-field="true" />
              <input id="import-file" type="file" name="file" accept=".csv" hidden />
              <button type="button" class="link-button" onclick="document.getElementById('import-file').click();">{{ t['import'] }}</button>
            </form>
            <a class="link" id="export-link" data-base-url="{{ url_for('export_csv') }}" data-require-message="{{ t['password_required'] }}" href="{{ url_for('export_csv') }}">{{ t['export'] }}</a>
          </div>
          <div class="nav-section nav-clock">
            <div class="clock-display" id="live-clock" aria-live="polite">--:--:--</div>
          </div>
        </nav>
      </header>

    <div class="tabs" role="tablist">
      <button class="tab-button active" id="tab-btn-add" data-tab-target="tab-add" role="tab" aria-controls="tab-add" aria-selected="true">{{ t['add_record'] }}</button>
      <button class="tab-button" id="tab-btn-routes" data-tab-target="tab-routes" role="tab" aria-controls="tab-routes" aria-selected="false" tabindex="-1">{{ t['routes_top'] }}</button>
      <button class="tab-button" id="tab-btn-entries" data-tab-target="tab-entries" role="tab" aria-controls="tab-entries" aria-selected="false" tabindex="-1">{{ t['last_entries'] }}</button>
      <button class="tab-button" id="tab-btn-trend" data-tab-target="tab-trend" role="tab" aria-controls="tab-trend" aria-selected="false" tabindex="-1">{{ t['trend_chart'] }}</button>
      <button class="tab-button" id="tab-btn-products" data-tab-target="tab-products" role="tab" aria-controls="tab-products" aria-selected="false" tabindex="-1">{{ t['product_lookup'] }}</button>
      <button class="tab-button" id="tab-btn-city" data-tab-target="tab-city" role="tab" aria-controls="tab-city" aria-selected="false" tabindex="-1">{{ t['city_products'] }}</button>
    </div>

    <div class="tab-panels">
      <section class="tab-panel active" id="tab-add" role="tabpanel" aria-labelledby="tab-btn-add">
        <div class="card">
          <h2>{{ t['add_record'] }}</h2>
          <form id="add-form" data-require-message="{{ t['password_required'] }}" hx-post="{{ url_for('add_entry', lang=lang) }}" hx-target="#entries, #routes" hx-select="#entries, #routes" hx-swap="outerHTML" hx-trigger="submit" hx-on::response-error="alert(event.detail.xhr.responseText || 'Save failed')">
            <input type="hidden" name="password" data-password-field="true" />
            <label>{{ t['city'] }}</label>
            <input id="city" name="city" list="cities" placeholder="Berlin" autocomplete="off" required />
            <datalist id="cities">{% for c in cities %}<option value="{{ c }}">{% endfor %}</datalist>

            <label>{{ t['product'] }}</label>
            <input id="product" name="product" list="products" placeholder="Copper" autocomplete="off" required />
            <datalist id="products">{% for p in products %}<option value="{{ p }}">{% endfor %}</datalist>

            <div class="row wrap">
              <div style="flex:1">
                <label>{{ t['price'] }}</label>
                <input name="price" type="number" inputmode="numeric" min="0" step="1" placeholder="0" required />
              </div>
              <div style="flex:1">
                <label for="percent-slider">{{ t['percent'] }}</label>
                <div class="percent-control">
                  <button type="button" class="percent-btn" data-percent-delta="-1">-1%</button>
                  <input id="percent-slider" name="percent" type="range" min="30" max="160" step="1" value="100" />
                  <button type="button" class="percent-btn" data-percent-delta="1">+1%</button>
                  <span id="percent-display" class="muted percent-display">100%</span>
                </div>
                <div class="percent-presets">
                  <button type="button" class="percent-preset" data-percent-value="80">80%</button>
                  <button type="button" class="percent-preset" data-percent-value="100">100%</button>
                  <button type="button" class="percent-preset" data-percent-value="120">120%</button>
                </div>
                <div
                  id="latest-autofill"
                  class="latest-autofill"
                  hidden
                  data-loading="{{ t['latest_autofill_loading']|e }}"
                  data-empty="{{ t['latest_autofill_missing']|e }}"
                  data-from="{{ t['latest_autofill_from']|e }}"
                  data-auto="{{ t['latest_autofill_auto']|e }}"
                  data-trend-up="{{ t['trend_up']|e }}"
                  data-trend-down="{{ t['trend_down']|e }}"
                  data-trend-flat="{{ t['trend_flat']|e }}"
                >
                  <div class="latest-autofill__label">{{ t['latest_autofill_label'] }}</div>
                  <div class="latest-autofill__content" id="latest-autofill-content"></div>
                </div>
              </div>
            </div>
            <div class="trend-field">
              <span class="trend-caption">{{ t['trend_hint'] }}</span>
              <input type="hidden" name="trend" value="flat" data-trend-input="true" />
              <div class="trend-toggle" role="group" aria-label="{{ t['trend'] }}">
                <label class="trend-option up" data-trend-option="up" role="checkbox" aria-checked="false" tabindex="0">
                  <input type="checkbox" data-trend-toggle="up" />
                  <span class="trend-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                      <path d="M12 5l7 7h-4v7h-6v-7H5l7-7z"></path>
                    </svg>
                  </span>
                  <span class="trend-text">{{ t['trend_up'] }}</span>
                </label>
                <label class="trend-option down" data-trend-option="down" role="checkbox" aria-checked="false" tabindex="0">
                  <input type="checkbox" data-trend-toggle="down" />
                  <span class="trend-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                      <path d="M12 19l-7-7h4V5h6v7h4l-7 7z"></path>
                    </svg>
                  </span>
                  <span class="trend-text">{{ t['trend_down'] }}</span>
                </label>
              </div>
            </div>
            <div class="spacer"></div>
            <label class="checkbox">
              <input type="checkbox" name="is_production_city" value="1" />
              <span>{{ t['production_city'] }}</span>
            </label>
            <div class="actions">
              <button type="submit">{{ t['save'] }}</button>
              <button class="secondary" type="reset">{{ t['reset'] }}</button>
            </div>
          </form>
        </div>
      </section>

      <section class="tab-panel" id="tab-routes" role="tabpanel" aria-labelledby="tab-btn-routes">
        <div class="card" id="routes" hx-swap-oob="true" hx-get="{{ url_for('routes_view', lang=lang) }}" hx-trigger="load, every 30s" hx-swap="outerHTML"></div>
      </section>

      <section class="tab-panel" id="tab-entries" role="tabpanel" aria-labelledby="tab-btn-entries">
        <div class="card" id="entries" hx-swap-oob="true" hx-get="{{ url_for('entries_table', lang=lang) }}" hx-trigger="load, every 15s" hx-swap="outerHTML"></div>
      </section>

      <section class="tab-panel" id="tab-trend" role="tabpanel" aria-labelledby="tab-btn-trend">
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
      </section>

      <section class="tab-panel" id="tab-products" role="tabpanel" aria-labelledby="tab-btn-products">
        <div class="card" id="product-lookup">
          <h2>{{ t['product_lookup'] }}</h2>
          <form id="lookup-form" hx-get="{{ url_for('product_prices', lang=lang) }}" hx-target="#product-lookup-results" hx-swap="outerHTML" hx-trigger="submit, change from:#lookup-sort">
            <div class="row wrap">
              <div>
                <label for="lookup-product">{{ t['product'] }}</label>
                <input id="lookup-product" name="product" list="lookup-products" placeholder="{{ t['product_lookup_placeholder'] }}" autocomplete="off" required />
                <datalist id="lookup-products">{% for p in products %}<option value="{{ p }}">{% endfor %}</datalist>
              </div>
              <div>
                <label for="lookup-sort">{{ t['sort_label'] }}</label>
                <select id="lookup-sort" name="sort">
                  <option value="asc" selected>{{ t['sort_price_low'] }}</option>
                  <option value="desc">{{ t['sort_price_high'] }}</option>
                </select>
              </div>
            </div>
            <div class="actions">
              <button type="submit">{{ t['search'] }}</button>
            </div>
          </form>
          <div class="spacer"></div>
          <div id="product-lookup-results" class="muted">{{ t['product_lookup_hint'] }}</div>
        </div>
      </section>

      <section class="tab-panel" id="tab-city" role="tabpanel" aria-labelledby="tab-btn-city">
        <div class="card" id="city-production">
          <h2>{{ t['city_products'] }}</h2>
          <form id="city-production-form" hx-get="{{ url_for('city_products', lang=lang) }}" hx-target="#city-production-results" hx-swap="outerHTML" hx-trigger="submit, change from:#production-city">
            <div class="row wrap">
              <div style="flex:1">
                <label for="production-city">{{ t['city'] }}</label>
                <input id="production-city" name="city" list="production-cities" placeholder="{{ t['city'] }}" autocomplete="off" required />
                <datalist id="production-cities">{% for c in cities %}<option value="{{ c }}">{% endfor %}</datalist>
              </div>
            </div>
            <div class="actions">
              <button type="submit">{{ t['search'] }}</button>
            </div>
          </form>
          <div class="spacer"></div>
          <div id="city-production-results" class="muted">{{ t['city_products_hint'] }}</div>
        </div>
      </section>
    </div>
  </div>

<script>
(function(){
'use strict';

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
bindTypeahead('lookup-product','lookup-products','product');
bindTypeahead('production-city','production-cities','city');

const navToggle = document.querySelector('[data-nav-toggle]');
const navMenu = document.getElementById('nav-menu');
const mobileNavQuery = window.matchMedia('(max-width: 900px)');

function closeNavMenu(){
  if(navToggle){
    navToggle.setAttribute('aria-expanded', 'false');
  }
  if(navMenu){
    navMenu.classList.remove('open');
  }
}

// Responsive nav toggle keeps the header usable on phones by collapsing the menu into a drawer.
if(navToggle && navMenu){
  navToggle.addEventListener('click', () => {
    const expanded = navToggle.getAttribute('aria-expanded') === 'true';
    const next = !expanded;
    navToggle.setAttribute('aria-expanded', String(next));
    navMenu.classList.toggle('open', next);
  });

  const handleNavBreakpoint = (event) => {
    if(!event.matches){
      closeNavMenu();
    }
  };

  if(mobileNavQuery.addEventListener){
    mobileNavQuery.addEventListener('change', handleNavBreakpoint);
  } else if(mobileNavQuery.addListener){
    mobileNavQuery.addListener(handleNavBreakpoint);
  }
}

const adminPasswordInput = document.getElementById('admin-password');
const importForm = document.getElementById('import-form');
const exportLink = document.getElementById('export-link');
const clockDisplay = document.getElementById('live-clock');
let clockState = null;
const tabButtons = Array.from(document.querySelectorAll('[data-tab-target]'));
const tabPanels = Array.from(document.querySelectorAll('.tab-panel'));
const addForm = document.getElementById('add-form');
const saveButton = addForm ? addForm.querySelector('button[type="submit"]') : null;
const priceInput = addForm ? addForm.querySelector('input[name="price"]') : null;
const trendInput = addForm ? addForm.querySelector('input[data-trend-input]') : null;
const trendToggleInputs = addForm ? Array.from(addForm.querySelectorAll('input[data-trend-toggle]')) : [];
const trendOptionLabels = addForm ? Array.from(addForm.querySelectorAll('[data-trend-option]')) : [];
const cityInput = document.getElementById('city');
const productInput = document.getElementById('product');
const productionCheckbox = addForm ? addForm.querySelector('input[name="is_production_city"]') : null;
const latestBox = document.getElementById('latest-autofill');
const latestContent = document.getElementById('latest-autofill-content');
const latestTexts = latestBox
  ? {
      loading: latestBox.dataset.loading || '',
      empty: latestBox.dataset.empty || '',
      from: latestBox.dataset.from || '',
      auto: latestBox.dataset.auto || '',
      trends: {
        up: latestBox.dataset.trendUp || '',
        down: latestBox.dataset.trendDown || '',
        flat: latestBox.dataset.trendFlat || '',
      },
    }
  : null;

function sanitizeNumeric(value){
  if(value === null || value === undefined){ return ''; }
  const normalized = String(value).replace(',', '.').trim();
  if(!normalized){ return ''; }
  const match = normalized.match(/^(\d+)/);
  return match ? match[1] : '';
}

function passwordMessage(target){
  return (target && target.dataset && target.dataset.requireMessage)
    || (adminPasswordInput && adminPasswordInput.dataset && adminPasswordInput.dataset.requireMessage)
    || 'Password required';
}

function flashElement(el){
  if(!el){ return; }
  el.classList.remove('pulse-highlight');
  void el.offsetWidth;
  el.classList.add('pulse-highlight');
  window.setTimeout(() => {
    el.classList.remove('pulse-highlight');
  }, 1300);
}

function padTime(value){
  return String(value).padStart(2, '0');
}

function renderClock(){
  if(!clockDisplay){ return; }
  if(!clockState){
    clockDisplay.textContent = '--:--:--';
    clockDisplay.removeAttribute('data-timezone');
    clockDisplay.removeAttribute('title');
    return;
  }
  const { hours, minutes, seconds, timezone } = clockState;
  clockDisplay.textContent = `${padTime(hours)}:${padTime(minutes)}:${padTime(seconds)}`;
  if(timezone){
    clockDisplay.setAttribute('data-timezone', timezone);
    clockDisplay.setAttribute('title', timezone);
  } else {
    clockDisplay.removeAttribute('data-timezone');
    clockDisplay.removeAttribute('title');
  }
}

function tickClock(){
  if(!clockState){ return; }
  let { hours, minutes, seconds } = clockState;
  seconds += 1;
  if(seconds >= 60){
    seconds = 0;
    minutes += 1;
    if(minutes >= 60){
      minutes = 0;
      hours = (hours + 1) % 24;
    }
  }
  clockState.hours = hours;
  clockState.minutes = minutes;
  clockState.seconds = seconds;
  renderClock();
}

async function syncClock(){
  if(!clockDisplay){ return; }
  try {
    const response = await fetch('/db-time.json', { headers: { 'Accept': 'application/json' } });
    if(!response.ok){ throw new Error('Failed to fetch db time'); }
    const payload = await response.json();
    const parts = (payload.time || '').split(':').map((part) => Number.parseInt(part, 10));
    if(parts.length >= 3 && parts.every((value) => Number.isFinite(value))){
      clockState = {
        hours: ((parts[0] % 24) + 24) % 24,
        minutes: ((parts[1] % 60) + 60) % 60,
        seconds: ((parts[2] % 60) + 60) % 60,
        timezone: payload.timezone || ''
      };
    } else if(payload.iso){
      const isoDate = new Date(payload.iso);
      if(!Number.isNaN(isoDate.getTime())){
        const offsetSeconds = Number(payload.offset_seconds);
        let reference = isoDate;
        if(Number.isFinite(offsetSeconds)){
          reference = new Date(isoDate.getTime() + offsetSeconds * 1000);
        }
        clockState = {
          hours: reference.getUTCHours(),
          minutes: reference.getUTCMinutes(),
          seconds: reference.getUTCSeconds(),
          timezone: payload.timezone || ''
        };
      } else {
        clockState = null;
      }
    } else {
      clockState = null;
    }
  } catch(err) {
    clockState = null;
  }
  renderClock();
}

function safeNumber(value){
  const num = Number(value);
  return Number.isNaN(num) ? null : num;
}

function formatPrice(value){
  const num = safeNumber(value);
  if(num === null){ return ''; }
  try {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(num);
  } catch(err) {
    return String(Math.round(num * 100) / 100);
  }
}

function formatPercent(value){
  const num = safeNumber(value);
  if(num === null){ return ''; }
  try {
    return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(num)}%`;
  } catch(err) {
    return `${Math.round(num)}%`;
  }
}

function formatTimestamp(iso){
  if(!iso){ return ''; }
  const date = new Date(iso);
  if(Number.isNaN(date.getTime())){ return ''; }
  try {
    return date.toLocaleString(undefined, { hour12: false });
  } catch(err) {
    return date.toISOString().replace('T', ' ').slice(0, 16);
  }
}

function describeLatestData(data){
  if(!data || !latestTexts){ return ''; }
  const pieces = [];
  const priceText = formatPrice(data.price);
  if(priceText){ pieces.push(priceText); }
  const trendKey = data.trend === 'down' ? 'down' : data.trend === 'up' ? 'up' : 'flat';
  const trendText = latestTexts.trends[trendKey] || '';
  if(trendText){ pieces.push(trendText); }
  if(data.percent !== null && data.percent !== undefined){
    const percentText = formatPercent(data.percent);
    if(percentText){ pieces.push(percentText); }
  }
  const timestamp = formatTimestamp(data.updated_at);
  if(timestamp){
    pieces.push(`${latestTexts.from} ${timestamp}`.trim());
  }
  const base = latestTexts.auto || '';
  const details = pieces.filter(Boolean).join(' · ');
  return details ? `${base} · ${details}` : base;
}

function setLatestState(state, text){
  if(!latestBox || !latestContent){ return; }
  latestBox.classList.remove('loading', 'success', 'empty');
  if(state === 'idle'){
    latestBox.hidden = true;
    latestBox.dataset.state = 'idle';
    latestContent.textContent = '';
    return;
  }
  latestBox.hidden = false;
  latestBox.dataset.state = state;
  if(state === 'loading'){
    latestBox.classList.add('loading');
    latestContent.textContent = latestTexts ? latestTexts.loading : '';
    return;
  }
  if(state === 'empty'){
    latestBox.classList.add('empty');
    latestContent.textContent = latestTexts ? latestTexts.empty : '';
    return;
  }
  latestBox.classList.add('success');
  latestContent.textContent = text || '';
}

function previewLatestFromDataset(dataset){
  if(!dataset){ return; }
  const payload = {
    price: dataset.price,
    trend: dataset.trend,
    percent: dataset.percent,
    updated_at: dataset.updated,
  };
  const text = describeLatestData(payload);
  if(text){
    setLatestState('success', text);
  }
}

function syncPasswordFields(){
  const pwd = adminPasswordInput ? adminPasswordInput.value.trim() : '';
  document.querySelectorAll('input[data-password-field]').forEach((input) => {
    input.value = pwd;
  });
  if(saveButton){
    saveButton.disabled = !pwd;
  }
}

function obtainPassword(target, options){
  const opts = Object.assign({ silent: false }, options || {});
  const pwd = adminPasswordInput ? adminPasswordInput.value.trim() : '';
  if(!pwd){
    if(!opts.silent){
      alert(passwordMessage(target));
    }
    if(adminPasswordInput){ adminPasswordInput.focus(); }
    syncPasswordFields();
    return null;
  }
  if(target && typeof target.querySelector === 'function'){
    const hidden = target.querySelector('input[data-password-field]');
    if(hidden){ hidden.value = pwd; }
  }
  syncPasswordFields();
  return pwd;
}

function attachPasswordGuard(form){
  if(!form){ return; }
  form.addEventListener('submit', (event) => {
    if(!obtainPassword(form)){
      form.dataset.passwordWarned = '1';
      event.preventDefault();
    } else {
      form.dataset.passwordWarned = '';
    }
  });
  form.addEventListener('htmx:configRequest', (event) => {
    const silent = form.dataset.passwordWarned === '1';
    form.dataset.passwordWarned = '';
    const pwd = obtainPassword(form, { silent });
    if(!pwd){
      event.preventDefault();
      return;
    }
    event.detail.parameters = event.detail.parameters || {};
    event.detail.parameters.password = pwd;
    event.detail.headers = event.detail.headers || {};
    event.detail.headers['X-Access-Password'] = pwd;
  });
}

function activateTab(id){
  if(!id){ return; }
  let found = false;
  tabButtons.forEach((btn) => {
    const active = btn.dataset.tabTarget === id;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
    btn.setAttribute('tabindex', active ? '0' : '-1');
    if(active){ found = true; }
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle('active', panel.id === id);
  });
  if(found){
    try {
      localStorage.setItem('tr-active-tab', id);
    } catch(err) {
      /* ignore */
    }
  }
}

(function initTabs(){
  if(!tabButtons.length || !tabPanels.length){ return; }
  let initialId = null;
  try {
    const stored = localStorage.getItem('tr-active-tab');
    if(stored && tabPanels.some((panel) => panel.id === stored)){
      initialId = stored;
    }
  } catch(err) {
    initialId = null;
  }
  if(!initialId){
    const defaultBtn = tabButtons.find((btn) => btn.classList.contains('active'));
    if(defaultBtn){ initialId = defaultBtn.dataset.tabTarget; }
  }
  if(initialId){
    activateTab(initialId);
  }
  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tabTarget));
    btn.addEventListener('keydown', (event) => {
      if(event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar'){
        event.preventDefault();
        activateTab(btn.dataset.tabTarget);
      }
    });
  });
})();

if(adminPasswordInput){
  adminPasswordInput.addEventListener('input', syncPasswordFields);
  syncPasswordFields();
}

if(exportLink){
  exportLink.addEventListener('click', (event) => {
    event.preventDefault();
    const pwd = obtainPassword(exportLink);
    if(!pwd){ return; }
    const base = exportLink.dataset.baseUrl || exportLink.getAttribute('href') || '/export.csv';
    const url = new URL(base, window.location.origin);
    const currentParams = new URLSearchParams(window.location.search);
    if(currentParams.has('lang') && !url.searchParams.has('lang')){
      url.searchParams.set('lang', currentParams.get('lang'));
    }
    url.searchParams.set('password', pwd);
    window.location.href = url.toString();
  });
}

if(clockDisplay){
  syncClock();
  window.setInterval(tickClock, 1000);
  window.setInterval(syncClock, 60000);
}

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

const percentSlider = document.getElementById('percent-slider');
const percentDisplay = document.getElementById('percent-display');
function sliderMetaFactory(){
  if(!percentSlider){
    return { min: null, max: null, defaultValue: null };
  }
  const parse = (value) => {
    if(value === null || value === undefined || value === ''){
      return null;
    }
    const num = Number(value);
    return Number.isNaN(num) ? null : num;
  };
  const min = parse(percentSlider.getAttribute('min'));
  const max = parse(percentSlider.getAttribute('max'));
  let defaultValue = parse(percentSlider.getAttribute('value'));
  if(defaultValue === null){
    defaultValue = parse(percentSlider.defaultValue);
  }
  if(defaultValue === null){
    defaultValue = 100;
  }
  return { min, max, defaultValue };
}

const sliderMeta = sliderMetaFactory();

attachPasswordGuard(addForm);
attachPasswordGuard(importForm);

function updatePercentDisplay(){
  if(percentSlider && percentDisplay){
    percentDisplay.textContent = `${percentSlider.value}%`;
  }
}

function setSliderValue(rawValue, options){
  if(!percentSlider){ return; }
  const opts = Object.assign({ fallback: sliderMeta.defaultValue }, options || {});
  let value = null;
  if(typeof rawValue === 'number' && !Number.isNaN(rawValue)){
    value = rawValue;
  } else if(typeof rawValue === 'string'){
    const trimmed = rawValue.trim();
    if(trimmed !== ''){
      const parsed = Number(trimmed);
      if(!Number.isNaN(parsed)){
        value = parsed;
      }
    }
  } else if(rawValue !== undefined && rawValue !== null){
    const parsed = Number(rawValue);
    if(!Number.isNaN(parsed)){
      value = parsed;
    }
  }
  if(value === null){
    const fallback = opts.fallback;
    if(fallback === undefined || fallback === null){
      return;
    }
    const parsedFallback = Number(fallback);
    if(Number.isNaN(parsedFallback)){
      return;
    }
    value = parsedFallback;
  }
  if(sliderMeta.min !== null){
    value = Math.max(sliderMeta.min, value);
  }
  if(sliderMeta.max !== null){
    value = Math.min(sliderMeta.max, value);
  }
  percentSlider.value = String(value);
  percentSlider.dispatchEvent(new Event('input', { bubbles: true }));
}

if(percentSlider){
  percentSlider.addEventListener('input', updatePercentDisplay);
}

updatePercentDisplay();

if(addForm){
  addForm.addEventListener('reset', () => {
    setLatestState('idle');
    lastLookupKey = '';
    lastLookupResult = null;
    pendingLookupKey = '';
    setTimeout(() => {
      setSliderValue(sliderMeta.defaultValue);
      setTrendValue(trendInput ? trendInput.defaultValue : 'flat');
    }, 0);
  });
  addForm.addEventListener('htmx:beforeRequest', () => {
    if(cityInput){
      addForm.dataset.lastCityValue = cityInput.value;
    }
  });
  addForm.addEventListener('htmx:afterRequest', (event) => {
    if(!event.detail || !event.detail.successful){
      return;
    }
    const preservedCity = addForm.dataset.lastCityValue || (cityInput ? cityInput.value : '');
    addForm.reset();
    syncPasswordFields();
    const schedule = window.requestAnimationFrame ? window.requestAnimationFrame.bind(window) : (cb) => setTimeout(cb, 0);
    schedule(() => {
      if(cityInput){
        cityInput.value = preservedCity;
        cityInput.dispatchEvent(new Event('input', { bubbles: true }));
        if(preservedCity){
          cityInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }
      if(productInput){
        productInput.value = '';
        productInput.focus();
      }
      delete addForm.dataset.lastCityValue;
    });
  });
}

document.querySelectorAll('[data-percent-delta]').forEach(btn => {
  btn.addEventListener('click', () => {
    if(!percentSlider){ return; }
    const delta = Number(btn.dataset.percentDelta || 0);
    if(Number.isNaN(delta)){ return; }
    const current = Number(percentSlider.value || sliderMeta.defaultValue || 0);
    setSliderValue(current + delta);
  });
});

document.querySelectorAll('.percent-preset').forEach(btn => {
  btn.addEventListener('click', () => {
    setSliderValue(btn.dataset.percentValue);
  });
});

function normalizeTrend(value){
  return value === 'up' || value === 'down' ? value : 'flat';
}

function setTrendValue(value){
  if(!trendInput){ return; }
  const normalized = normalizeTrend(value);
  trendInput.value = normalized;
  trendToggleInputs.forEach((checkbox) => {
    const match = checkbox.dataset.trendToggle === normalized;
    checkbox.checked = match;
  });
  trendOptionLabels.forEach((label) => {
    const match = label.dataset.trendOption === normalized;
    label.classList.toggle('active', match);
    label.setAttribute('aria-checked', match ? 'true' : 'false');
  });
}

if(trendToggleInputs.length){
  trendToggleInputs.forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const targetValue = checkbox.checked ? checkbox.dataset.trendToggle : 'flat';
      setTrendValue(targetValue);
    });
  });
  trendOptionLabels.forEach((label) => {
    label.addEventListener('keydown', (event) => {
      if(event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar'){
        event.preventDefault();
        const checkbox = label.querySelector('input[data-trend-toggle]');
        if(!checkbox){ return; }
        const willActivate = !checkbox.checked;
        setTrendValue(willActivate ? checkbox.dataset.trendToggle : 'flat');
      }
    });
  });
  setTrendValue(trendInput ? trendInput.value : 'flat');
}

let latestRequestId = 0;
let autofillTimer = null;
let lastLookupKey = '';
let lastLookupResult = null;
let pendingLookupKey = '';

function applyEntryToForm(dataset){
  if(cityInput){
    cityInput.value = dataset.city || '';
  }
  if(productInput){
    productInput.value = dataset.product || '';
  }
  if(priceInput){
    const sanitized = sanitizeNumeric(dataset.price);
    priceInput.value = sanitized;
    flashElement(priceInput);
  }
  setTrendValue(dataset.trend);
  if(productionCheckbox){
    productionCheckbox.checked = dataset.production === '1' || dataset.production === 'true';
  }
  setSliderValue(dataset.percent);
  if(percentSlider){
    flashElement(percentSlider);
  }
  previewLatestFromDataset(dataset);
  queueAutofillLatestEntry(true);
}
document.body.addEventListener('htmx:afterSwap', (event) => {
  if(adminPasswordInput){
    syncPasswordFields();
  }
});

document.body.addEventListener('click', (event) => {
  const row = event.target.closest ? event.target.closest('tr.entry-row') : null;
  if(row && row.closest('#entries')){
    applyEntryToForm(row.dataset);
  }
});

async function autofillLatestEntry(key, city, product){
  const requestId = ++latestRequestId;
  pendingLookupKey = key;
  try {
    const params = new URLSearchParams({ city, product });
    const res = await fetch(`/latest-entry.json?${params.toString()}`);
    if(requestId !== latestRequestId || pendingLookupKey !== key){
      return;
    }
    if(!res.ok){
      throw new Error('lookup failed');
    }
    const data = await res.json();
    if(requestId !== latestRequestId || pendingLookupKey !== key){
      return;
    }
    pendingLookupKey = '';
    if(!data || !data.found){
      lastLookupKey = key;
      lastLookupResult = { found: false, text: '' };
      setLatestState('empty');
      return;
    }
    const description = describeLatestData(data);
    lastLookupKey = key;
    lastLookupResult = { found: true, data, text: description };
    setLatestState('success', description);
    if(priceInput && data.price !== null && data.price !== undefined){
      const sanitized = sanitizeNumeric(data.price);
      if(sanitized){
        const before = priceInput.value;
        priceInput.value = sanitized;
        if(before !== sanitized){
          flashElement(priceInput);
        }
        if(before.trim() === ''){
          priceInput.focus();
          if(typeof priceInput.select === 'function'){
            priceInput.select();
          }
        }
      }
    }
    if(typeof data.trend === 'string'){
      setTrendValue(data.trend);
    }
    if(productionCheckbox){
      productionCheckbox.checked = Boolean(data.is_production_city);
    }
    const beforePercent = percentSlider ? percentSlider.value : null;
    setSliderValue(data.percent, { fallback: sliderMeta.defaultValue });
    if(percentSlider && beforePercent !== null && beforePercent !== percentSlider.value){
      flashElement(percentSlider);
    }
  } catch(err) {
    if(requestId === latestRequestId && pendingLookupKey === key){
      setLatestState('empty');
    }
    console.warn('latest entry lookup failed', err);
  } finally {
    if(pendingLookupKey === key){
      pendingLookupKey = '';
    }
  }
}

function queueAutofillLatestEntry(force){
  if(!cityInput || !productInput){ return; }
  const city = cityInput.value.trim();
  const product = productInput.value.trim();
  if(!city || !product){
    setLatestState('idle');
    lastLookupKey = '';
    lastLookupResult = null;
    pendingLookupKey = '';
    return;
  }
  const key = `${city.toLowerCase()}::${product.toLowerCase()}`;
  if(!force && lastLookupKey === key && lastLookupResult){
    if(lastLookupResult.found){
      setLatestState('success', lastLookupResult.text);
    } else {
      setLatestState('empty');
    }
    return;
  }
  if(autofillTimer){
    clearTimeout(autofillTimer);
  }
  setLatestState('loading');
  autofillTimer = setTimeout(() => {
    autofillTimer = null;
    autofillLatestEntry(key, city, product);
  }, force ? 60 : 160);
}

if(cityInput){
  cityInput.addEventListener('input', () => queueAutofillLatestEntry(false));
  cityInput.addEventListener('change', () => {
    queueAutofillLatestEntry(true);
    if(productInput && !productInput.value){
      productInput.focus();
    }
  });
}
if(productInput){
  productInput.addEventListener('input', () => queueAutofillLatestEntry(false));
  productInput.addEventListener('change', () => {
    queueAutofillLatestEntry(true);
    if(priceInput && !priceInput.value){
      priceInput.focus();
      if(typeof priceInput.select === 'function'){
        priceInput.select();
      }
    }
  });
}

if(priceInput){
  priceInput.addEventListener('input', () => {
    const sanitized = sanitizeNumeric(priceInput.value);
    if(priceInput.value !== sanitized){
      priceInput.value = sanitized;
    }
  });
  priceInput.addEventListener('blur', () => {
    const sanitized = sanitizeNumeric(priceInput.value);
    if(priceInput.value !== sanitized){
      priceInput.value = sanitized;
    }
  });
}

if(cityInput && productInput && cityInput.value && productInput.value){
  queueAutofillLatestEntry(true);
}

wireChartSelectors();
})();
</script>
</body>
</html>
"""

ENTRIES_TABLE = r"""
<div class="card" id="entries" hx-swap-oob="true">
  <details class="collapsible" open>
    <summary>
      <h2>{{ t['last_entries'] }}</h2>
      <span class="summary-meta">{{ items|length }} {{ t['entries_count'] }}</span>
      <span class="summary-icon" aria-hidden="true">▾</span>
    </summary>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{{ t['when'] }}</th>
            <th>{{ t['city'] }}</th>
            <th>{{ t['product'] }}</th>
            <th class="center">{{ t['production_city_short'] }}</th>
            <th class="right">{{ t['price'] }}</th>
            <th>{{ t['trend'] }}</th>
            <th class="right">{{ t['percent'] }}</th>
          </tr>
        </thead>
        <tbody>
        {% for e in items %}
        <tr class="entry-row" title="{{ t['click_to_fill'] }}" data-city="{{ e['city'] }}" data-product="{{ e['product'] }}" data-price="{{ e['price'] }}" data-trend="{{ e['trend'] or 'flat' }}" data-percent="{{ '' if e['percent'] is none else e['percent'] }}" data-production="{{ 1 if e['is_production_city'] else 0 }}" data-updated="{{ e['created_at'] }}">
            <td class="nowrap">{{ e['created_at'][:19].replace('T',' ') }}</td>
            <td>{{ e['city'] }}</td>
            <td>{{ e['product'] }}</td>
            <td class="center">{{ '✓' if e['is_production_city'] else '—' }}</td>
            <td class="right">{{ '%.0f'|format(e['price']) }}</td>
            <td>
              {% set tcode = e['trend'] or 'flat' %}
              <span class="pill {{ tcode }}">{{ { 'up': t['trend_up'], 'down': t['trend_down'], 'flat': t['trend_flat'] }[tcode] }}</span>
            </td>
            <td class="right">{{ ('%.0f%%'|format(e['percent'])) if e['percent'] is not none else '—' }}</td>
          </tr>
        {% else %}
          <tr><td colspan="7" class="muted">{{ t['no_data'] }}</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </details>
</div>
"""

ROUTES_TABLE = r"""
<div class="card" id="routes" hx-swap-oob="true">
  <h2>{{ t['routes_top'] }}</h2>
  <div class="table-scroll">
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
          <td class="right">{{ '%.0f'|format(r['from_price']) }}</td>
          <td class="right">{{ '%.0f'|format(r['to_price']) }}</td>
          <td class="right">{{ '%.0f'|format(r['profit_abs']) }}</td>
          <td class="right">
            {% if r['profit_pct'] is not none %}
              {{ '%.0f%%'|format(r['profit_pct']) }}
            {% else %}
              —
            {% endif %}
          </td>
        </tr>
        {% else %}
        <tr><td colspan="7" class="muted">{{ t['no_routes'] }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""

PRODUCT_PRICES_TABLE = r"""
<div id="product-lookup-results">
  {% if product %}
    <p class="muted">{{ t['prices_for'] }} "{{ product }}" · {{ t['sort_label'] }}: {{ t['sort_price_low'] if sort == 'asc' else t['sort_price_high'] }}</p>
  {% endif %}
  {% if items %}
  <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th>{{ t['city'] }}</th>
          <th class="center">{{ t['production_city_short'] }}</th>
          <th class="right">{{ t['price'] }}<span class="sort-indicator">{{ '↑' if sort == 'asc' else '↓' }}</span></th>
          <th>{{ t['trend'] }}</th>
          <th class="right">{{ t['percent'] }}</th>
          <th>{{ t['when'] }}</th>
        </tr>
      </thead>
      <tbody>
      {% for e in items %}
        <tr>
          <td>{{ e['city'] }}</td>
          <td class="center">{{ '✓' if e['is_production_city'] else '—' }}</td>
          <td class="right">{{ '%.0f'|format(e['price']) }}</td>
          <td>
            {% set tcode = e['trend'] or 'flat' %}
            <span class="pill {{ tcode }}">{{ { 'up': t['trend_up'], 'down': t['trend_down'], 'flat': t['trend_flat'] }[tcode] }}</span>
          </td>
          <td class="right">{{ ('%.0f%%'|format(e['percent'])) if e['percent'] is not none else '—' }}</td>
          <td class="nowrap">{{ e['created_at'][:19].replace('T',' ') }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
    <p class="muted">{{ message }}</p>
  {% endif %}
</div>
"""

CITY_PRODUCTS_TABLE = r"""
<div id="city-production-results">
  {% if city %}
    <p class="muted">{{ t['city_products_for'] }} "{{ city }}"</p>
  {% endif %}
  {% if items %}
  <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th>{{ t['product'] }}</th>
          <th class="right">{{ t['price'] }}</th>
          <th>{{ t['trend'] }}</th>
          <th class="right">{{ t['percent'] }}</th>
          <th>{{ t['when'] }}</th>
        </tr>
      </thead>
      <tbody>
      {% for e in items %}
        <tr>
          <td>{{ e['product'] }}</td>
          <td class="right">{{ '%.0f'|format(e['price']) }}</td>
          <td>
            {% set tcode = e['trend'] or 'flat' %}
            <span class="pill {{ tcode }}">{{ { 'up': t['trend_up'], 'down': t['trend_down'], 'flat': t['trend_flat'] }[tcode] }}</span>
          </td>
          <td class="right">{{ ('%.0f%%'|format(e['percent'])) if e['percent'] is not none else '—' }}</td>
          <td class="nowrap">{{ e['created_at'][:19].replace('T',' ') }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
    <p class="muted">{{ message }}</p>
  {% endif %}
</div>
"""

# ---------------------- Queries & logic ----------------------

def distinct_values(field: str, limit: int | None = None) -> List[str]:
    assert field in ("city", "product")
    sql = f"SELECT DISTINCT {field} FROM entries ORDER BY {field} ASC"
    params: tuple[Any, ...]
    if limit:
        sql += " LIMIT %s"
        params = (limit,)
    else:
        params = ()
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return [row[field] for row in cur.fetchall()]


def latest_entry_for(city: str, product: str) -> Dict[str, Any] | None:
    sql = """
    SELECT price, trend, percent, is_production_city, created_at
    FROM entries
    WHERE city = %s AND product = %s
    ORDER BY created_at DESC
    LIMIT 1
    """
    with get_conn() as conn:
        row = conn.execute(sql, (city, product)).fetchone()
    return dict(row) if row else None


def latest_prices_view() -> List[Dict[str, Any]]:
    sql = r"""
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, product, MAX(created_at) AS mx
        FROM entries
        GROUP BY city, product
      ) m
      ON e.city = m.city AND e.product = m.product AND e.created_at = m.mx
    )
    SELECT * FROM latest ORDER BY created_at DESC LIMIT 250
    """
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return rows_to_dicts(rows)


def compute_routes(limit: int = 25) -> List[Dict[str, Any]]:
    sql = r"""
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, product, MAX(created_at) AS mx
        FROM entries
        GROUP BY city, product
      ) m
      ON e.city = m.city AND e.product = m.product AND e.created_at = m.mx
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
    WHERE b.price > a.price AND a.is_production_city IS TRUE
    ORDER BY profit_pct DESC, profit_abs DESC
    LIMIT %s
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(row) for row in rows]


def product_latest_prices(product: str, sort: str = "asc") -> List[Dict[str, Any]]:
    order = "DESC" if sort == "desc" else "ASC"
    sql = f"""
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, MAX(created_at) AS mx
        FROM entries
        WHERE product = %s
        GROUP BY city
      ) m
      ON e.city = m.city AND e.created_at = m.mx
      WHERE e.product = %s
    )
    SELECT * FROM latest ORDER BY price {order}, created_at DESC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (product, product)).fetchall()
    return rows_to_dicts(rows)


def city_production_products(city: str) -> List[Dict[str, Any]]:
    sql = r"""
    WITH latest AS (
      SELECT DISTINCT ON (product) e.*
      FROM entries e
      WHERE e.city = %s AND e.is_production_city IS TRUE
      ORDER BY product, created_at DESC
    )
    SELECT * FROM latest ORDER BY product ASC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (city,)).fetchall()
    return rows_to_dicts(rows)

# ---------------------- Routes ----------------------

@app.get("/db-time.json")
def database_time():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT now() AS db_now, to_char(now(), 'HH24:MI:SS') AS local_time, current_setting('TIMEZONE') AS tz"
        ).fetchone()

    if not row:
        abort(500, "Database time unavailable")

    row = dict(row)

    db_now = row.get("db_now")
    tz_name = row.get("tz") or ""
    payload: Dict[str, Any] = {
        "time": row.get("local_time"),
        "timezone": tz_name,
    }

    if isinstance(db_now, datetime):
        payload["iso"] = _as_utc(db_now).isoformat(timespec="seconds")
        offset = db_now.utcoffset()
        if offset is not None:
            payload["offset_seconds"] = int(offset.total_seconds())

    return jsonify(payload)

@app.get("/")
def index():
    lang = get_lang()
    t = STRINGS[lang]
    toggle_lang = 'en' if lang=='ru' else 'ru'
    # Начальные значения в datalist: по 50 штук
    cities = distinct_values("city", limit=50)
    products = distinct_values("product", limit=50)
    resp = make_response(
        render_fragment(
            BASE_HTML,
            lang=lang,
            title=f"{APP_TITLE} | {t['title']}",
            app_name=APP_TITLE,
            toggle_lang=toggle_lang,
            cities=cities,
            products=products,
        )
    )
    resp.set_cookie('lang', lang, max_age=60*60*24*365)
    return resp


@app.get("/latest-entry.json")
def latest_entry_json():
    city = (request.args.get("city") or "").strip()
    product = (request.args.get("product") or "").strip()
    if not city or not product:
        return jsonify({"found": False})

    row = latest_entry_for(city, product)
    if not row:
        return jsonify({"found": False})

    created_at = row.get("created_at")
    return jsonify(
        {
            "found": True,
            "price": row.get("price"),
            "trend": row.get("trend"),
            "percent": row.get("percent"),
            "is_production_city": row.get("is_production_city"),
            "updated_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
        }
    )


@app.post("/add")
def add_entry():
    def bad(msg: str):
        return make_response(msg, 400)

    lang = get_lang()
    guard = ensure_password(lang)
    if guard is not None:
        return guard

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
        if not 30 <= percent <= 160:
            return bad("Percent must be between 30 and 160")

    if trend not in ("up", "down", "flat"):
        trend = "flat"

    is_production_city = bool(request.form.get("is_production_city"))

    created_at = datetime.now(timezone.utc)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO entries(city, product, price, trend, percent, is_production_city, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (city, product, price, trend, percent, is_production_city, created_at),
        )

    lang = get_lang()
    return render_entries_and_routes(lang)

@app.get("/entries")
def entries_table():
    lang = get_lang()
    return render_fragment(ENTRIES_TABLE, lang=lang, items=latest_prices_view())


@app.get("/product-prices")
def product_prices():
    lang = get_lang()
    product = (request.args.get("product") or "").strip()
    sort = (request.args.get("sort") or "asc").strip().lower()
    sort = "desc" if sort == "desc" else "asc"
    if not product:
        message = STRINGS[lang]["product_lookup_hint"]
        return render_fragment(
            PRODUCT_PRICES_TABLE,
            lang=lang,
            items=[],
            product=None,
            message=message,
            sort=sort,
        )

    rows = product_latest_prices(product, sort=sort)
    message = STRINGS[lang]["no_prices"]
    return render_fragment(
        PRODUCT_PRICES_TABLE,
        lang=lang,
        items=rows,
        product=product,
        message=message,
        sort=sort,
    )


@app.get("/city-products")
def city_products():
    lang = get_lang()
    city = (request.args.get("city") or "").strip()
    if not city:
        message = STRINGS[lang]["city_products_hint"]
        return render_fragment(
            CITY_PRODUCTS_TABLE,
            lang=lang,
            items=[],
            city=None,
            message=message,
        )

    rows = city_production_products(city)
    message = STRINGS[lang]["city_products_no_data"]
    return render_fragment(
        CITY_PRODUCTS_TABLE,
        lang=lang,
        items=rows,
        city=city,
        message=message,
    )


@app.get("/routes")
def routes_view():
    lang = get_lang()
    return render_fragment(ROUTES_TABLE, lang=lang, routes=compute_routes())

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
        sql += f" WHERE LOWER({field}) LIKE %s"
        params = (like,)
    else:
        params = ()
    sql += f" ORDER BY {field} ASC LIMIT 20"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([row[field] for row in rows])

@app.get("/series.json")
def series_json():
    city = (request.args.get('city') or '').strip()
    product = (request.args.get('product') or '').strip()
    if not city or not product:
        return jsonify([])
    sql = (
        "SELECT created_at AS ts, price, trend, percent FROM entries "
        "WHERE city=%s AND product=%s ORDER BY created_at ASC"
    )
    with get_conn() as conn:
        rows = conn.execute(sql, (city, product)).fetchall()
    data = []
    for r in rows:
        item = dict(r)
        ts = item.get("ts")
        if isinstance(ts, datetime):
            item["ts"] = _as_utc(ts).isoformat(timespec="seconds")
        data.append(item)
    return jsonify(data)


@app.post("/import.csv")
def import_csv_route():
    lang = get_lang()
    guard = ensure_password(lang)
    if guard is not None:
        return guard

    uploaded = request.files.get("file")
    if not uploaded or uploaded.filename == "":
        return make_response("CSV file required", 400)

    try:
        content = uploaded.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return make_response("CSV must be UTF-8", 400)

    if not content.strip():
        return make_response("Empty CSV", 400)

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return make_response("Missing CSV header", 400)

    rows: List[tuple[Any, ...]] = []
    for row in reader:
        city = (row.get("city") or "").strip()
        product = (row.get("product") or "").strip()
        price_raw = str(row.get("price") or "").replace(",", ".").strip()
        if not city or not product or not price_raw:
            continue
        try:
            price = float(price_raw)
        except ValueError:
            continue
        if price < 0:
            continue

        trend = (row.get("trend") or "flat").strip().lower()
        if trend not in ("up", "down", "flat"):
            trend = "flat"

        percent_raw = row.get("percent")
        percent = None
        if percent_raw not in (None, ""):
            try:
                percent = float(str(percent_raw).replace(",", "."))
            except ValueError:
                percent = None

        is_prod_raw = row.get("is_production_city")
        is_production = False
        if isinstance(is_prod_raw, str):
            is_production = is_prod_raw.strip().lower() in {"1", "true", "yes", "y", "да"}
        elif is_prod_raw is not None:
            is_production = bool(is_prod_raw)

        created_raw = row.get("created_at") or row.get("timestamp")
        created_at = datetime.now(timezone.utc)
        if created_raw:
            try:
                created_at = datetime.fromisoformat(str(created_raw).strip())
            except ValueError:
                created_at = datetime.now(timezone.utc)
        created_at = _as_utc(created_at)

        rows.append((city, product, price, trend, percent, is_production, created_at))

    if not rows:
        return make_response("No valid rows found", 400)

    sql = (
        "INSERT INTO entries(city, product, price, trend, percent, is_production_city, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)"
    )
    with get_conn() as conn:
        for record in rows:
            conn.execute(sql, record)

    return render_entries_and_routes(lang)


@app.get("/export.csv")
def export_csv():
    lang = get_lang()
    guard = ensure_password(lang)
    if guard is not None:
        return guard

    sql = "SELECT * FROM entries ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id",
        "created_at",
        "city",
        "product",
        "price",
        "trend",
        "percent",
        "is_production_city",
    ])
    for r in rows:
        created_at = r["created_at"]
        if isinstance(created_at, datetime):
            created_at = _as_utc(created_at).isoformat(timespec="seconds")
        is_prod = r["is_production_city"]
        if isinstance(is_prod, bool):
            is_prod = int(is_prod)
        percent_val = r["percent"]
        writer.writerow([
            r["id"],
            created_at,
            r["city"],
            r["product"],
            r["price"],
            r["trend"],
            "" if percent_val is None else percent_val,
            is_prod,
        ])
    csv_data = buffer.getvalue()
    resp = make_response(csv_data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=entries.csv"
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
