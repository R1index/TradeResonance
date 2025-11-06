"""Service helpers for working with entries and related queries."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Dict, Iterable, List, Tuple

import sqlalchemy as sa
from sqlalchemy import text

from ..extensions import db
from ..models import Entry, PendingEntry


CacheBuilder = Callable[[], List[str]]
_cache: Dict[str, Tuple[datetime, List[str]]] = {}


def cached_list(key: str, factory: CacheBuilder, ttl_seconds: int = 60) -> List[str]:
    now = datetime.utcnow()
    if key in _cache:
        ts, value = _cache[key]
        if now - ts < timedelta(seconds=ttl_seconds):
            return value
    value = factory()
    _cache[key] = (now, value)
    return value


def latest_entries_subquery() -> sa.sql.Select:
    ts = sa.func.coalesce(Entry.updated_at, Entry.created_at).label("ts")
    rn = sa.func.row_number().over(
        partition_by=(Entry.city, Entry.product),
        order_by=sa.desc(ts),
    ).label("rn")

    base = sa.select(
        Entry.id,
        Entry.city,
        Entry.product,
        Entry.price,
        Entry.trend,
        Entry.percent,
        Entry.is_production_city,
        Entry.created_at,
        Entry.updated_at,
        ts,
        rn,
    ).subquery()

    columns = [col for col in base.c if col.key != "rn"]
    return sa.select(*columns).where(base.c.rn == 1).subquery()


def approve_pending(entry: PendingEntry) -> None:
    existing = Entry.query.filter_by(city=entry.city, product=entry.product).first()
    if existing:
        existing.price = entry.price
        existing.trend = entry.trend
        existing.percent = entry.percent
        existing.is_production_city = existing.is_production_city or entry.is_production_city
    else:
        created = Entry(
            city=entry.city,
            product=entry.product,
            price=entry.price,
            trend=entry.trend,
            percent=entry.percent,
            is_production_city=entry.is_production_city,
        )
        db.session.add(created)
    db.session.delete(entry)
    db.session.commit()
    dedupe_entries()


def dedupe_entries() -> None:
    rows: Iterable[Entry] = (
        db.session.query(Entry)
        .order_by(
            Entry.city.asc(),
            Entry.product.asc(),
            Entry.updated_at.desc().nullslast(),
            Entry.created_at.desc(),
        )
        .all()
    )

    keep: Dict[Tuple[str, str], Entry] = {}
    to_delete: List[int] = []
    for entry in rows:
        key = (entry.city.strip(), entry.product.strip())
        if key not in keep:
            keep[key] = entry
            continue
        if entry.is_production_city and not keep[key].is_production_city:
            keep[key].is_production_city = True
        to_delete.append(entry.id)

    if to_delete:
        Entry.query.filter(Entry.id.in_(to_delete)).delete(synchronize_session=False)
    db.session.commit()


def setup_database(app) -> None:
    with app.app_context():
        db.create_all()
        dedupe_entries()
        database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        try:
            if database_uri.startswith("sqlite"):
                db.session.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_entries_product_updated "
                        "ON entries (product, updated_at DESC, created_at DESC)"
                    )
                )
                db.session.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_entries_city_updated "
                        "ON entries (city, updated_at DESC, created_at DESC)"
                    )
                )
            db.session.commit()
        except Exception as exc:  # pragma: no cover - defensive
            app.logger.warning("Index creation warning: %s", exc)
            db.session.rollback()
