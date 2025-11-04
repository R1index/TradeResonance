
import os
from flask import Flask
from .extensions import db

def create_app():
    app = Flask(__name__)

    # Config
    app.config.from_object('config.Config')

    # DB init
    db.init_app(app)

    with app.app_context():
        # Ensure tables exist in dev only
        if app.config.get('CREATE_TABLES_ON_START'):
            from .models import Entry  # noqa
            db.create_all()

    # Blueprints
    from .routes.main import bp as main_bp
    from .routes.admin import bp as admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Simple healthcheck
    @app.get('/healthz')
    def healthz():
        try:
            db.session.execute(db.text('SELECT 1'))
            return {'ok': True}, 200
        except Exception as e:
            return {'ok': False, 'error': str(e)}, 500

    return app
