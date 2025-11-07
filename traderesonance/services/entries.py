"""Service helpers for working with entries and related queries."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import load_only

from ..extensions import db
from ..models import Entry, EntrySnapshot, PendingEntry


CacheBuilder = Callable[[], List[str]]
_cache: Dict[str, Tuple[datetime, List[str]]] = {}
_value_cache: Dict[str, Tuple[datetime, Any]] = {}


def cached_list(key: str, factory: CacheBuilder, ttl_seconds: int = 60) -> List[str]:
    now = datetime.utcnow()
    if key in _cache:
        ts, value = _cache[key]
        if now - ts < timedelta(seconds=ttl_seconds):
            return value
    value = factory()
    _cache[key] = (now, value)
    return value


def cached_value(key: str, factory: Callable[[], Any], ttl_seconds: int = 60) -> Any:
    now = datetime.utcnow()
    if key in _value_cache:
        ts, value = _value_cache[key]
        if now - ts < timedelta(seconds=ttl_seconds):
            return value
    value = factory()
    _value_cache[key] = (now, value)
    return value


def product_image_map() -> Dict[str, Optional[str]]:
    def build() -> Dict[str, Optional[str]]:
        rows = (
            db.session.query(
                Entry.product,
                Entry.image_path,
                Entry.updated_at,
                Entry.created_at,
            )
            .order_by(
                Entry.product.asc(),
                Entry.updated_at.desc().nullslast(),
                Entry.created_at.desc(),
            )
            .all()
        )

        result: Dict[str, Optional[str]] = {}
        for product, image_path, *_ in rows:
            if product not in result:
                result[product] = image_path
            elif not result[product] and image_path:
                result[product] = image_path
        return result

    return cached_value("product_image_map", build, ttl_seconds=120)


def invalidate_product_image_cache() -> None:
    _value_cache.pop("product_image_map", None)


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
        Entry.image_path,
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
    trimmed_city = sa.func.trim(Entry.city)
    trimmed_product = sa.func.trim(Entry.product)

    duplicate_keys: Iterable[Tuple[str, str]] = (
        db.session.query(
            trimmed_city.label("city"), trimmed_product.label("product")
        )
        .group_by(trimmed_city, trimmed_product)
        .having(sa.func.count(Entry.id) > 1)
        .all()
    )

    if not duplicate_keys:
        return

    order_columns = (
        Entry.updated_at.desc().nullslast(),
        Entry.created_at.desc(),
        Entry.id.desc(),
    )

    ids_to_delete: List[int] = []
    modified = False

    for norm_city, norm_product in duplicate_keys:
        entries: List[Entry] = (
            Entry.query.options(
                load_only(
                    Entry.id,
                    Entry.city,
                    Entry.product,
                    Entry.image_path,
                    Entry.is_production_city,
                    Entry.updated_at,
                    Entry.created_at,
                )
            )
            .filter(trimmed_city == norm_city, trimmed_product == norm_product)
            .order_by(*order_columns)
            .all()
        )

        if not entries:
            continue

        keep = entries[0]
        merged_is_production = bool(keep.is_production_city)
        merged_image = keep.image_path

        for extra in entries[1:]:
            if extra.is_production_city and not merged_is_production:
                merged_is_production = True
            if not merged_image and extra.image_path:
                merged_image = extra.image_path
            ids_to_delete.append(extra.id)

        if keep.is_production_city != merged_is_production:
            keep.is_production_city = merged_is_production
            modified = True
        if keep.image_path != merged_image:
            keep.image_path = merged_image
            modified = True

    if ids_to_delete:
        Entry.query.filter(Entry.id.in_(ids_to_delete)).delete(
            synchronize_session=False
        )
        modified = True

    if not modified:
        return

    db.session.commit()
    invalidate_product_image_cache()


def setup_database(app) -> None:
    with app.app_context():
        db.create_all()

        try:
            inspector = sa.inspect(db.engine)
            entry_columns = {col["name"] for col in inspector.get_columns("entries")}
            if "image_path" not in entry_columns:
                db.session.execute(
                    sa.text("ALTER TABLE entries ADD COLUMN image_path VARCHAR(255)")
                )
                db.session.commit()
        except Exception:  # pragma: no cover - defensive upgrade path
            db.session.rollback()

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
