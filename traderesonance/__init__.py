"""Application factory for Trade Resonance."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask

from .config import load_config
from .extensions import db
from .routes import register as register_routes
from .services.entries import setup_database

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(config_override: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        template_folder=str(BASE_DIR / "templates"),
    )
    app.config.update(load_config())
    if config_override:
        app.config.update(config_override)

    images_subdir = "product-images"
    upload_dir = BASE_DIR / "static" / images_subdir
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config.setdefault("PRODUCT_IMAGE_SUBDIR", images_subdir)
    app.config.setdefault("PRODUCT_IMAGE_UPLOAD_FOLDER", str(upload_dir))
    app.config.setdefault("PRODUCT_IMAGE_SIZE", (200, 200))

    db.init_app(app)
    setup_database(app)
    register_routes(app)
    return app


__all__ = ["create_app", "db"]
