from flask import Flask
from .config import Config
from .db import init_db_pool, close_db_pool
from .routes import register_blueprints

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # Init DB
    init_db_pool(app.config["DATABASE_URL"])

    # Blueprints
    register_blueprints(app)

    # Teardown
    @app.teardown_appcontext
    def _shutdown_session(exception=None):
        close_db_pool()

    # Health check + simple CLI
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.cli.command("dbcheck")
    def dbcheck():
        from .db import one
        try:
            row = one("SELECT 1 as ok")
            print("DB OK:", row)
        except Exception as e:
            print("DB ERROR:", e)
            raise

    return app
