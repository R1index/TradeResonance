from .home import bp as home_bp
from .prices import bp as prices_bp
from .cities import bp as cities_bp
from .products import bp as products_bp

def register_blueprints(app):
    app.register_blueprint(home_bp)
    app.register_blueprint(prices_bp, url_prefix="/prices")
    app.register_blueprint(cities_bp, url_prefix="/cities")
    app.register_blueprint(products_bp, url_prefix="/products")
