"""Database models for Trade Resonance."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .extensions import db


class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    city = db.Column(db.String(120), nullable=False, index=True)
    product = db.Column(db.String(120), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    trend = db.Column(db.String(10), nullable=False)
    percent = db.Column(db.Float, nullable=False, default=0.0)
    is_production_city = db.Column(db.Boolean, nullable=False, default=False)

    def updated_or_created(self) -> Optional[datetime]:
        return self.updated_at or self.created_at


class PendingEntry(db.Model):
    __tablename__ = "pending_entries"

    id = db.Column(db.Integer, primary_key=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    city = db.Column(db.String(120), nullable=False, index=True)
    product = db.Column(db.String(120), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    trend = db.Column(db.String(10), nullable=False)
    percent = db.Column(db.Float, nullable=False, default=0.0)
    is_production_city = db.Column(db.Boolean, nullable=False, default=False)
    submit_ip = db.Column(db.String(64))
