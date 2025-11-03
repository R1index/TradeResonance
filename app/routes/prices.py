from flask import Blueprint, request, render_template, flash
from ..services.prices_service import list_prices, create_price, delete_price, cities, products

bp = Blueprint("prices", __name__)

@bp.get("/")
def page():
    items = list_prices(limit=50, offset=0)
    return render_template("partials/price_rows.html", items=items)

@bp.post("/create")
def create():
    city = request.form.get("city", "").strip()
    product = request.form.get("product", "").strip()
    price = request.form.get("price", "").strip()
    try:
        create_price(city, product, float(price))
        flash("Saved", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    # HTMX запрос обновляет только таблицу
    return page()

@bp.post("/delete/<int:price_id>")
def remove(price_id:int):
    delete_price(price_id)
    return page()

@bp.get("/options/cities")
def options_cities():
    opts = cities()
    return render_template("partials/options.html", items=opts)

@bp.get("/options/products")
def options_products():
    opts = products()
    return render_template("partials/options.html", items=opts)
