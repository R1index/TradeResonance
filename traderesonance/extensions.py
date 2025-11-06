"""Application extensions.

This module is intentionally tiny and isolates third-party extension
instances so they can be imported without creating circular imports.
"""
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy database instance shared across the project.
db = SQLAlchemy()
