"""Simple localisation helpers used across templates and routes."""
from __future__ import annotations

from datetime import datetime
from typing import Dict
from flask import request, session


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
        "edit_existing": "Entry already exists. Redirected to edit.",
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
        "dedupe": "Deduplicate",
        "items": "items",
        "pairs": "pairs",
        "redirect": "Redirect to",
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
        "edit_existing": "Запись уже существует. Перенаправляем на редактирование.",
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
        "dedupe": "Удалить дубликаты",
        "items": "тов.",
        "pairs": "пар",
        "redirect": "Перейти после",
    },
}


def get_lang() -> str:
    lang = request.args.get("lang") or session.get("lang") or "ru"
    if lang not in STRINGS:
        lang = "en"
    session["lang"] = lang
    return lang


def translate(key: str) -> str:
    lang = get_lang()
    return STRINGS.get(lang, STRINGS["en"]).get(key, key)


def context_processor():
    """Context processor injecting translation helpers into templates."""
    return {
        "t": translate,
        "lang": get_lang(),
        "current_year": datetime.utcnow().year,
    }
