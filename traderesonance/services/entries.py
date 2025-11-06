"""Service helpers for working with entries and related queries."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar, cast

import sqlalchemy as sa
from sqlalchemy import text

from ..extensions import db
from ..models import Entry, EntrySnapshot, PendingEntry


T = TypeVar("T")


CacheBuilder = Callable[[], T]
_cache: Dict[str, Tuple[datetime, Any]] = {}


def cached_value(key: str, factory: CacheBuilder, ttl_seconds: int = 60) -> T:
    now = datetime.utcnow()
    if key in _cache:
        ts, value = _cache[key]
        if now - ts < timedelta(seconds=ttl_seconds):
            return cast(T, value)
    value = factory()
    _cache[key] = (now, value)
    return value


def cached_list(key: str, factory: Callable[[], List[str]], ttl_seconds: int = 60) -> List[str]:
    return cached_value(key, factory, ttl_seconds)


def cached_product_images(ttl_seconds: int = 60) -> Dict[str, str]:
    def _factory() -> Dict[str, str]:
        rows = (
            db.session.query(
                Entry.product,
                Entry.image_path,
                Entry.updated_at,
                Entry.created_at,
            )
            .filter(Entry.image_path.isnot(None))
            .order_by(Entry.updated_at.desc().nullslast(), Entry.created_at.desc())
            .all()
        )
        result: Dict[str, str] = {}
        for product, image_path, _, _ in rows:
            if not image_path:
                continue
            if product not in result:
                result[product] = image_path
        return result

    return cached_value("product_images", _factory, ttl_seconds)


def invalidate_cache(key: str) -> None:
    _cache.pop(key, None)


def record_snapshot(entry: Entry, *, recorded_at: Optional[datetime] = None) -> None:
    """Persist a historical snapshot for the provided entry state."""

    if not entry:
        return

    recorded_at = recorded_at or datetime.utcnow()

    last_snapshot = (
        EntrySnapshot.query.filter(
            EntrySnapshot.city == entry.city,
            EntrySnapshot.product == entry.product,
        )
        .order_by(EntrySnapshot.recorded_at.desc(), EntrySnapshot.id.desc())
        .first()
    )

    if last_snapshot and (
        last_snapshot.price == entry.price
        and last_snapshot.percent == entry.percent
        and last_snapshot.trend == entry.trend
        and last_snapshot.is_production_city == entry.is_production_city
    ):
        return

    snapshot = EntrySnapshot(
        entry_id=entry.id,
        recorded_at=recorded_at,
        city=entry.city,
        product=entry.product,
        price=entry.price,
        trend=entry.trend,
        percent=entry.percent,
        is_production_city=entry.is_production_city,
    )
    db.session.add(snapshot)


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
        db.session.flush()
        record_snapshot(existing)
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
        db.session.flush()
        record_snapshot(created)
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

        created_snapshots = 0
        for entry in Entry.query.all():
            has_snapshot = (
                EntrySnapshot.query.filter(
                    EntrySnapshot.city == entry.city,
                    EntrySnapshot.product == entry.product,
                )
                .order_by(EntrySnapshot.recorded_at.desc(), EntrySnapshot.id.desc())
                .first()
            )
            if not has_snapshot:
                record_snapshot(entry, recorded_at=entry.updated_or_created() or datetime.utcnow())
                created_snapshots += 1
        if created_snapshots:
            db.session.commit()

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
