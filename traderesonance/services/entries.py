"""Domain services for working with trade entries and analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy import func, select, text
from sqlalchemy.orm import Query

from ..extensions import db
from ..models import Entry, PendingEntry
from ..utils import parse_bool

CacheBuilder = Callable[[], List[str]]
_CACHE: Dict[str, Tuple[datetime, List[str]]] = {}
_CACHE_TTL_SECONDS = 120


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def cached_list(key: str, factory: CacheBuilder, ttl_seconds: int = _CACHE_TTL_SECONDS) -> List[str]:
    """Cache a short list of strings in-memory.

    The application is single-process on Railway, so a simple in-process
    cache is sufficient and avoids hammering the database for every
    request.  Data is refreshed in the background every ``ttl_seconds``.
    """

    now = datetime.utcnow()
    if key in _CACHE:
        ts, value = _CACHE[key]
        if now - ts < timedelta(seconds=ttl_seconds):
            return value
    value = factory()
    _CACHE[key] = (now, value)
    return value


def invalidate_cache(*keys: str) -> None:
    if not keys:
        _CACHE.clear()
        return
    for key in keys:
        _CACHE.pop(key, None)


# ---------------------------------------------------------------------------
# Dataclasses for view-models
# ---------------------------------------------------------------------------


@dataclass
class PriceTotals:
    entries: int
    cities: int
    products: int


@dataclass
class PaginationWindow:
    page: int
    pages: int
    total: int
    per_page: int
    has_prev: bool
    has_next: bool
    prev_page: Optional[int]
    next_page: Optional[int]
    window: Sequence[int]


@dataclass
class PricePage:
    items: Sequence[Entry]
    pagination: PaginationWindow
    totals: PriceTotals


@dataclass
class CityGroup:
    city: str
    entries: Sequence[Entry]


@dataclass
class RouteItem:
    product: str
    buy_price: float
    sell_price: float
    margin: float
    margin_percent: float
    buy_entry_id: int
    sell_entry_id: int
    buy_trend: str
    sell_trend: str
    buy_percent: float
    sell_percent: float
    buy_updated: datetime
    sell_updated: datetime


@dataclass
class RouteGroup:
    buy_city: str
    sell_city: str
    entries: Sequence[RouteItem]
    items_total: int
    sum_profit: float
    avg_margin: float
    updated_at: datetime


@dataclass
class RoutePage:
    groups: Sequence[RouteGroup]
    pagination: PaginationWindow


# ---------------------------------------------------------------------------
# Filter dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PriceFilters:
    city: str = ""
    product: str = ""
    trend: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    percent_min: Optional[float] = None
    percent_max: Optional[float] = None
    production: str = "any"
    sort: str = "updated_desc"

    @classmethod
    def from_args(cls, args) -> "PriceFilters":
        def parse_float(name: str) -> Optional[float]:
            value = args.get(name)
            if value in (None, ""):
                return None
            try:
                return float(value)
            except ValueError:
                return None

        return cls(
            city=(args.get("city") or "").strip(),
            product=(args.get("product") or "").strip(),
            trend=(args.get("trend") or "").strip().lower(),
            price_min=parse_float("price_min"),
            price_max=parse_float("price_max"),
            percent_min=parse_float("percent_min"),
            percent_max=parse_float("percent_max"),
            production=(args.get("prod") or "any").strip().lower(),
            sort=(args.get("sort") or "updated_desc").strip().lower(),
        )

    def apply(self, query: Query) -> Query:
        if self.city:
            query = query.filter(Entry.city.ilike(f"%{self.city}%"))
        if self.product:
            query = query.filter(Entry.product.ilike(f"%{self.product}%"))
        if self.trend in {"up", "down"}:
            query = query.filter(Entry.trend == self.trend)
        if self.price_min is not None:
            query = query.filter(Entry.price >= self.price_min)
        if self.price_max is not None:
            query = query.filter(Entry.price <= self.price_max)
        if self.percent_min is not None:
            query = query.filter(Entry.percent >= self.percent_min)
        if self.percent_max is not None:
            query = query.filter(Entry.percent <= self.percent_max)
        if self.production == "yes":
            query = query.filter(Entry.is_production_city.is_(True))
        elif self.production == "no":
            query = query.filter(Entry.is_production_city.is_(False))
        return query

    def sort_clause(self):  # noqa: ANN001 - SQLAlchemy expression
        sort_map = {
            "price_asc": Entry.price.asc(),
            "price_desc": Entry.price.desc(),
            "percent_asc": Entry.percent.asc(),
            "percent_desc": Entry.percent.desc(),
            "updated_asc": Entry.updated_at.asc().nullslast(),
            "updated_desc": Entry.updated_at.desc().nullslast(),
        }
        return sort_map.get(self.sort, sort_map["updated_desc"])


@dataclass
class CityFilters:
    mode: str = "any"

    @classmethod
    def from_args(cls, args) -> "CityFilters":
        mode = (args.get("pf") or "any").strip().lower()
        if mode not in {"any", "only_prod", "only_nonprod"}:
            mode = "any"
        return cls(mode=mode)

    def allow(self, is_production_city: bool) -> bool:
        if self.mode == "only_prod":
            return is_production_city
        if self.mode == "only_nonprod":
            return not is_production_city
        return True


@dataclass
class RouteFilters:
    product: str = ""
    buy_city: str = ""
    sell_city: str = ""
    buy_only_prod: bool = False
    min_profit: Optional[float] = None
    min_margin: Optional[float] = None
    min_buy_percent: Optional[float] = None
    min_sell_percent: Optional[float] = None
    buy_trend: str = ""
    sell_trend: str = ""
    max_age_value: Optional[int] = None
    max_age_unit: str = "h"
    top_k: int = 3
    min_items: int = 1
    max_items: int = 50
    sort_by: str = "sum_profit_desc"
    page: int = 1
    per_page: int = 10

    @classmethod
    def from_args(cls, args) -> "RouteFilters":
        def parse_int(name: str) -> Optional[int]:
            value = args.get(name)
            if value in (None, ""):
                return None
            try:
                return int(value)
            except ValueError:
                return None

        def parse_float(name: str) -> Optional[float]:
            value = args.get(name)
            if value in (None, ""):
                return None
            try:
                return float(value)
            except ValueError:
                return None

        return cls(
            product=(args.get("product") or "").strip(),
            buy_city=(args.get("buy_city") or "").strip(),
            sell_city=(args.get("sell_city") or "").strip(),
            buy_only_prod=parse_bool(args.get("buy_only_prod")),
            min_profit=parse_float("min_profit"),
            min_margin=parse_float("min_margin"),
            min_buy_percent=parse_float("min_buy_percent"),
            min_sell_percent=parse_float("min_sell_percent"),
            buy_trend=(args.get("buy_trend") or "").strip().lower(),
            sell_trend=(args.get("sell_trend") or "").strip().lower(),
            max_age_value=parse_int("max_age_value"),
            max_age_unit=(args.get("max_age_unit") or "h").strip().lower() or "h",
            top_k=max(1, min(10, parse_int("k") or 3)),
            min_items=max(1, min(1000, parse_int("min_items") or 1)),
            max_items=max(1, min(1000, parse_int("max_items") or 50)),
            sort_by=(args.get("sort_by") or "sum_profit_desc").strip().lower(),
            page=max(1, parse_int("page") or 1),
            per_page=max(1, min(100, parse_int("per_page") or 10)),
        )

    def age_limit_seconds(self) -> Optional[int]:
        if not self.max_age_value:
            return None
        unit_map = {"m": 60, "h": 3600, "d": 86400}
        multiplier = unit_map.get(self.max_age_unit, 3600)
        return self.max_age_value * multiplier


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _build_pagination(paginate_obj, window: int = 7) -> PaginationWindow:
    start = max(1, paginate_obj.page - window // 2)
    end = min(paginate_obj.pages, start + window - 1)
    start = max(1, end - window + 1)
    return PaginationWindow(
        page=paginate_obj.page,
        pages=paginate_obj.pages,
        total=paginate_obj.total,
        per_page=paginate_obj.per_page,
        has_prev=paginate_obj.has_prev,
        has_next=paginate_obj.has_next,
        prev_page=paginate_obj.prev_num,
        next_page=paginate_obj.next_num,
        window=list(range(start, end + 1)),
    )


def _stats_for_query(query: Query) -> PriceTotals:
    base = query.order_by(None)
    counts = base.with_entities(
        func.count(Entry.id),
        func.count(func.distinct(Entry.city)),
        func.count(func.distinct(Entry.product)),
    ).first()
    entries_total, cities_total, products_total = counts or (0, 0, 0)
    return PriceTotals(
        entries=entries_total or 0,
        cities=cities_total or 0,
        products=products_total or 0,
    )


def fetch_price_page(filters: PriceFilters, page: int, per_page: int) -> PricePage:
    per_page = max(1, min(500, per_page))
    base_query = filters.apply(Entry.query)
    ordered = base_query.order_by(filters.sort_clause(), Entry.id.desc())
    pagination = db.paginate(ordered, page=page, per_page=per_page, error_out=False)
    totals = _stats_for_query(base_query)
    return PricePage(items=pagination.items, pagination=_build_pagination(pagination), totals=totals)


def fetch_city_groups(filters: CityFilters) -> Sequence[CityGroup]:
    latest = latest_entries_subquery()
    stmt = (
        select(
            latest.c.id,
            latest.c.city,
            latest.c.product,
            latest.c.price,
            latest.c.trend,
            latest.c.percent,
            latest.c.is_production_city,
            latest.c.created_at,
            latest.c.updated_at,
        )
        .select_from(latest)
        .order_by(latest.c.city.asc(), latest.c.product.asc())
    )

    rows = db.session.execute(stmt).all()
    grouped: Dict[str, List[Entry]] = {}
    for row in rows:
        entry = Entry(
            id=row.id,
            city=row.city,
            product=row.product,
            price=row.price,
            trend=row.trend,
            percent=row.percent,
            is_production_city=row.is_production_city,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        if not filters.allow(entry.is_production_city):
            continue
        grouped.setdefault(entry.city, []).append(entry)

    result: List[CityGroup] = []
    for city, entries in sorted(grouped.items(), key=lambda item: item[0].lower()):
        result.append(CityGroup(city=city, entries=entries))
    return result


def fetch_route_page(filters: RouteFilters) -> RoutePage:
    latest = latest_entries_subquery()
    stmt = select(latest).select_from(latest)
    if filters.product:
        stmt = stmt.where(latest.c.product.ilike(f"%{filters.product}%"))
    rows = db.session.execute(stmt).all()

    entries: Dict[str, Dict[str, Entry]] = {}
    for row in rows:
        entry = Entry(
            id=row.id,
            city=row.city,
            product=row.product,
            price=row.price,
            trend=row.trend,
            percent=row.percent,
            is_production_city=row.is_production_city,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        entries.setdefault(entry.city, {})[entry.product] = entry

    groups: List[RouteGroup] = []
    age_limit = filters.age_limit_seconds()
    now = datetime.utcnow()

    for buy_city, buy_products in entries.items():
        if filters.buy_city and filters.buy_city.lower() not in buy_city.lower():
            continue
        if filters.buy_only_prod and not any(e.is_production_city for e in buy_products.values()):
            continue
        for sell_city, sell_products in entries.items():
            if buy_city == sell_city:
                continue
            if filters.sell_city and filters.sell_city.lower() not in sell_city.lower():
                continue
            common = set(buy_products).intersection(sell_products)
            if not common:
                continue

            items: List[RouteItem] = []
            for product in common:
                buy_entry = buy_products[product]
                if filters.buy_only_prod and not buy_entry.is_production_city:
                    continue
                sell_entry = sell_products[product]
                margin = sell_entry.price - buy_entry.price
                if filters.min_profit is not None and margin < filters.min_profit:
                    continue
                if buy_entry.price:
                    margin_percent = (margin / buy_entry.price) * 100
                else:
                    margin_percent = 0
                if filters.min_margin is not None and margin_percent < filters.min_margin:
                    continue
                if filters.min_buy_percent is not None and (buy_entry.percent or 0) < filters.min_buy_percent:
                    continue
                if filters.min_sell_percent is not None and (sell_entry.percent or 0) < filters.min_sell_percent:
                    continue
                if filters.buy_trend in {"up", "down"} and buy_entry.trend != filters.buy_trend:
                    continue
                if filters.sell_trend in {"up", "down"} and sell_entry.trend != filters.sell_trend:
                    continue
                buy_ts = buy_entry.updated_at or buy_entry.created_at
                sell_ts = sell_entry.updated_at or sell_entry.created_at
                if age_limit:
                    latest_ts = max(buy_ts, sell_ts)
                    if (now - latest_ts).total_seconds() > age_limit:
                        continue
                items.append(
                    RouteItem(
                        product=product,
                        buy_price=buy_entry.price,
                        sell_price=sell_entry.price,
                        margin=margin,
                        margin_percent=margin_percent,
                        buy_entry_id=buy_entry.id,
                        sell_entry_id=sell_entry.id,
                        buy_trend=buy_entry.trend,
                        sell_trend=sell_entry.trend,
                        buy_percent=buy_entry.percent,
                        sell_percent=sell_entry.percent,
                        buy_updated=buy_entry.updated_at or buy_entry.created_at,
                        sell_updated=sell_entry.updated_at or sell_entry.created_at,
                    )
                )

            if not items:
                continue

            items.sort(key=lambda item: item.margin, reverse=True)
            top_items = items[: filters.top_k]
            sum_profit = sum(item.margin for item in top_items)
            avg_margin = sum(item.margin_percent for item in top_items) / len(top_items)
            latest_update = max(item.buy_updated for item in top_items)
            latest_update = max(latest_update, max(item.sell_updated for item in top_items))

            groups.append(
                RouteGroup(
                    buy_city=buy_city,
                    sell_city=sell_city,
                    entries=top_items,
                    items_total=len(items),
                    sum_profit=sum_profit,
                    avg_margin=avg_margin,
                    updated_at=latest_update,
                )
            )

    groups = [g for g in groups if filters.min_items <= g.items_total <= filters.max_items]

    sort_map = {
        "sum_profit_desc": lambda g: (-g.sum_profit, -g.avg_margin),
        "avg_margin_desc": lambda g: (-g.avg_margin, -g.sum_profit),
        "count_desc": lambda g: (-g.items_total, -g.sum_profit),
        "fresh_desc": lambda g: (-g.updated_at.timestamp(), -g.sum_profit),
    }
    sorter = sort_map.get(filters.sort_by, sort_map["sum_profit_desc"])
    groups.sort(key=sorter)

    total = len(groups)
    pages = max(1, (total + filters.per_page - 1) // filters.per_page)
    page = min(filters.page, pages)
    start = (page - 1) * filters.per_page
    end = start + filters.per_page
    page_groups = groups[start:end]

    pagination = PaginationWindow(
        page=page,
        pages=pages,
        total=total,
        per_page=filters.per_page,
        has_prev=page > 1,
        has_next=page < pages,
        prev_page=page - 1 if page > 1 else None,
        next_page=page + 1 if page < pages else None,
        window=list(range(max(1, page - 3), min(pages, page + 3) + 1)),
    )
    return RoutePage(groups=page_groups, pagination=pagination)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def save_entry(
    *,
    city: str,
    product: str,
    price: float,
    trend: str,
    percent: float,
    is_production_city: bool,
) -> Entry:
    existing = Entry.query.filter(
        func.lower(Entry.city) == func.lower(city),
        func.lower(Entry.product) == func.lower(product),
    ).first()

    if existing:
        existing.price = price
        existing.trend = trend
        existing.percent = percent
        existing.is_production_city = existing.is_production_city or is_production_city
        db.session.commit()
        invalidate_cache("cities", "products")
        return existing

    entry = Entry(
        city=city,
        product=product,
        price=price,
        trend=trend,
        percent=percent,
        is_production_city=is_production_city,
    )
    db.session.add(entry)
    db.session.commit()
    invalidate_cache("cities", "products")
    return entry


def approve_pending(entry: PendingEntry) -> Entry:
    saved = save_entry(
        city=entry.city,
        product=entry.product,
        price=entry.price,
        trend=entry.trend,
        percent=entry.percent,
        is_production_city=entry.is_production_city,
    )
    db.session.delete(entry)
    db.session.commit()
    dedupe_entries()
    return saved


def create_pending(
    *,
    city: str,
    product: str,
    price: float,
    trend: str,
    percent: float,
    is_production_city: bool,
    submit_ip: Optional[str] = None,
) -> PendingEntry:
    pending = PendingEntry(
        city=city,
        product=product,
        price=price,
        trend=trend,
        percent=percent,
        is_production_city=is_production_city,
        submit_ip=submit_ip,
    )
    db.session.add(pending)
    db.session.commit()
    invalidate_cache("cities", "products")
    return pending


def update_entry(entry: Entry, data: Dict[str, object]) -> Entry:
    if "price" in data:
        entry.price = float(data["price"])
    if "trend" in data:
        entry.trend = str(data["trend"]).strip()
    if "percent" in data:
        entry.percent = float(data["percent"])
    if "is_production_city" in data:
        entry.is_production_city = bool(data["is_production_city"])
    db.session.commit()
    dedupe_entries()
    invalidate_cache("cities", "products")
    return entry


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
    invalidate_cache("cities", "products")


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


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def import_rows(rows: Iterable[Dict[str, str]]) -> int:
    count = 0
    for row in rows:
        city = (row.get("city") or "").strip()
        product = (row.get("product") or "").strip()
        if not city or not product:
            continue
        try:
            price = float(row.get("price", 0) or 0)
        except (TypeError, ValueError):
            price = 0
        trend = (row.get("trend") or "up").strip()
        try:
            percent = float(row.get("percent", 0) or 0)
        except (TypeError, ValueError):
            percent = 0
        is_prod = parse_bool(row.get("is_production_city"))
        created_at_str = row.get("created_at")
        updated_at_str = row.get("updated_at")
        created_at = None
        updated_at = None
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except ValueError:
                created_at = None
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            except ValueError:
                updated_at = None

        existing = Entry.query.filter_by(city=city, product=product).first()
        if existing:
            existing.price = price
            existing.trend = trend
            existing.percent = percent
            existing.is_production_city = existing.is_production_city or is_prod
            if created_at and not existing.created_at:
                existing.created_at = created_at
            if updated_at:
                existing.updated_at = updated_at
        else:
            db.session.add(
                Entry(
                    city=city,
                    product=product,
                    price=price,
                    trend=trend,
                    percent=percent,
                    is_production_city=is_prod,
                    created_at=created_at or datetime.utcnow(),
                    updated_at=updated_at,
                )
            )
        count += 1
    db.session.commit()
    dedupe_entries()
    invalidate_cache("cities", "products")
    return count


def export_rows(
    filters: PriceFilters,
    *,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
) -> Iterable[Entry]:
    query = filters.apply(Entry.query)
    if created_from:
        query = query.filter(Entry.created_at >= created_from)
    if created_to:
        query = query.filter(Entry.created_at <= created_to)
    query = query.order_by(Entry.created_at.desc())
    return query.all()


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------


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


__all__ = [
    "cached_list",
    "fetch_price_page",
    "fetch_city_groups",
    "fetch_route_page",
    "PriceFilters",
    "CityFilters",
    "RouteFilters",
    "PricePage",
    "RoutePage",
    "RouteGroup",
    "RouteItem",
    "CityGroup",
    "approve_pending",
    "create_pending",
    "update_entry",
    "save_entry",
    "dedupe_entries",
    "setup_database",
    "import_rows",
    "export_rows",
]
