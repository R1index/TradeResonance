from flask import Blueprint, render_template
from ..services.cities_service import city_list

bp = Blueprint("cities", __name__)

@bp.get("/options")
def options():
    return render_template("partials/options.html", items=city_list())
