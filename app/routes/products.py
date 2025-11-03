from flask import Blueprint, render_template
from ..services.products_service import product_list

bp = Blueprint("products", __name__)

@bp.get("/options")
def options():
    return render_template("partials/options.html", items=product_list())
