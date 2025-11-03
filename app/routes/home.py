from flask import Blueprint, render_template, jsonify
from ..services.prices_service import list_prices

bp = Blueprint("home", __name__)

@bp.get("/")
def index():
    # TODO: Передайте реальные данные для графика/таблицы
    latest = list_prices(limit=10, offset=0)
    return render_template("index.html", latest=latest)

@bp.get("/chart-data")
def chart_data():
    # TODO: Вернуть реальные агрегаты по датам/городам/товарам
    sample = {
        "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "datasets": [{
            "label": "Avg Price",
            "data": [10, 12, 11, 13, 12]
        }]
    }
    return jsonify(sample)
