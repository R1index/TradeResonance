"""Application factory for Trade Resonance."""
from __future__ import annotations

import os
import shutil
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

    _configure_upload_storage(app)

    db.init_app(app)
    setup_database(app)
    register_routes(app)
    return app


def _configure_upload_storage(app: Flask) -> None:
    """Ensure uploaded images survive redeployments."""

    static_root = Path(app.static_folder)
    uploads_dir = static_root / "uploads"

    # Railway mounts persistent volumes to this environment variable. Allow an
    # explicit override for other platforms as well.
    base_path = (
        os.environ.get("UPLOADS_ROOT")
        or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        or ""
    )

    target_root = Path(base_path).expanduser() if base_path else uploads_dir
    if target_root == uploads_dir:
        target_root.mkdir(parents=True, exist_ok=True)
        app.config["UPLOADS_FOLDER_PATH"] = str(target_root)
        return

    target_root.mkdir(parents=True, exist_ok=True)

    if uploads_dir.exists() and not uploads_dir.is_symlink():
        # Move any existing files from the ephemeral directory to the
        # persistent location so we do not lose images during the first run.
        for item in uploads_dir.iterdir():
            destination = target_root / item.name
            if destination.exists():
                continue
            shutil.move(str(item), destination)
        uploads_dir.rmdir()

    if not uploads_dir.exists():
        uploads_dir.symlink_to(target_root, target_is_directory=True)

    app.config["UPLOADS_FOLDER_PATH"] = str(target_root)


__all__ = ["create_app", "db"]
