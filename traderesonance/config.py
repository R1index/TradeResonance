"""Configuration helpers for the Trade Resonance application."""
from __future__ import annotations

import os
from typing import Dict, Any


DEFAULTS = {
    "SECRET_KEY": "dev-secret-change-me",
    "ADMIN_PASSWORD": "reso2025",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "SQLALCHEMY_ENGINE_OPTIONS": {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    },
    "DATABASE_URL": "sqlite:///local.db",
}


def _normalize_database_url(url: str) -> str:
    """Normalise DATABASE_URL for SQLAlchemy."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def load_config() -> Dict[str, Any]:
    """Collect runtime configuration from the environment."""
    secret_key = os.environ.get("SECRET_KEY", DEFAULTS["SECRET_KEY"])
    admin_password = os.environ.get("ADMIN_PASSWORD", DEFAULTS["ADMIN_PASSWORD"])
    raw_db_url = os.environ.get("DATABASE_URL", DEFAULTS["DATABASE_URL"])
    database_url = _normalize_database_url(raw_db_url)

    config = {
        "SECRET_KEY": secret_key,
        "ADMIN_PASSWORD": admin_password,
        "SQLALCHEMY_DATABASE_URI": database_url,
        "SQLALCHEMY_TRACK_MODIFICATIONS": DEFAULTS["SQLALCHEMY_TRACK_MODIFICATIONS"],
        "SQLALCHEMY_ENGINE_OPTIONS": DEFAULTS["SQLALCHEMY_ENGINE_OPTIONS"].copy(),
    }
    return config
