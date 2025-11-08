"""HTTP route declarations."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

import sqlalchemy as sa
from flask import (
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func

from ..extensions import db
from ..localization import context_processor, get_lang, translate
from ..models import Entry, EntrySnapshot, PendingEntry
from ..services.entries import (
    approve_pending,
    cached_list,
    dedupe_entries,
    latest_entries_subquery,
    invalidate_product_image_cache,
    product_image_map,
    record_snapshot,
)
from ..utils import parse_bool, safe_next


def register(app) -> None:
    app.context_processor(context_processor)

    app.add_url_rule("/", view_func=index)
    app.add_url_rule("/entries/new", view_func=new_entry, methods=["GET", "POST"])
    app.add_url_rule(
        "/entries/<int:entry_id>/edit",
        view_func=edit_entry,
        methods=["GET", "POST"],
    )
    app.add_url_rule("/import", view_func=import_csv, methods=["GET", "POST"])
    app.add_url_rule("/export.csv", view_func=export_csv)
    app.add_url_rule("/admin/dedupe", view_func=admin_dedupe)
    app.add_url_rule("/health", view_func=health)

    app.register_error_handler(404, not_found)
    app.register_error_handler(500, internal_error)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

UPLOAD_SUBDIR = "uploads"
TARGET_IMAGE_SIZE = (200, 200)

def _redirect_to_edit(
    entry_id: int,
    lang: str,
    *,
    next_url: Optional[str] = None,
    price: Optional[float] = None,
    percent: Optional[float] = None,
    trend: Optional[str] = None,
):
    params: Dict[str, Optional[str]] = {"entry_id": entry_id, "lang": lang}
    if next_url:
        params["next"] = next_url
    if price not in (None, ""):
        params["price"] = price
    if percent not in (None, ""):
        params["percent"] = percent
    if trend not in (None, ""):
        params["trend"] = trend
    return redirect(url_for("edit_entry", **params))


def _save_entry_image(file_storage) -> str:
    file_storage.stream.seek(0)
    try:
        with Image.open(file_storage.stream) as img:
            processed = ImageOps.fit(
                img.convert("RGBA"),
                TARGET_IMAGE_SIZE,
                Image.LANCZOS,
            )
            upload_folder = Path(
                current_app.config.get(
                    "UPLOADS_FOLDER_PATH",
                    Path(current_app.static_folder) / UPLOAD_SUBDIR,
                )
            )
            upload_folder.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid4().hex}.png"
            output_path = upload_folder / filename
            processed.save(output_path, format="PNG")
    except (UnidentifiedImageError, OSError):
        raise ValueError("invalid_image") from None
    finally:
        file_storage.stream.seek(0)

    return f"{UPLOAD_SUBDIR}/{filename}"


def _delete_image_file(relative_path: Optional[str]) -> None:
    if not relative_path:
        return

    static_root = Path(current_app.static_folder)
    target_path = static_root / relative_path
    try:
        target_path.relative_to(static_root)
    except ValueError:
        return

    if target_path.exists():
        try:
            target_path.unlink()
        except OSError:
            current_app.logger.warning("Failed to remove image %s", target_path)


def _build_product_suggestions(products: List[str]) -> List[Dict[str, Optional[str]]]:
    if not products:
        return []

    image_map = product_image_map()
    suggestions: List[Dict[str, Optional[str]]] = []
    for name in products:
        image_path = image_map.get(name)
        suggestions.append(
            {
                "name": name,
                "image": url_for("static", filename=image_path) if image_path else None,
            }
        )
    return suggestions


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def index():  # noqa: C901 - the view is complex but mirrored from legacy code
    lang = get_lang()
    tab = request.args.get("tab", "prices")

    if tab == "prices":
        q_city = (request.args.get("city") or "").strip()
        q_product = (request.args.get("product") or "").strip()
        q_trend = (request.args.get("trend") or "").strip()
        q_price_min = request.args.get("price_min", type=float)
        q_price_max = request.args.get("price_max", type=float)
        q_percent_min = request.args.get("percent_min", type=float)
        q_percent_max = request.args.get("percent_max", type=float)
        q_prod = (request.args.get("prod") or "any").strip().lower()
        q_sort = (request.args.get("sort") or "updated_desc").strip().lower()

        page = request.args.get("page", 1, type=int)
        per_page = max(1, min(500, request.args.get("per_page", 15, type=int)))

        query = Entry.query
        if q_city:
            query = query.filter(Entry.city.ilike(f"%{q_city}%"))
        if q_product:
            query = query.filter(Entry.product.ilike(f"%{q_product}%"))
        if q_trend in ("up", "down"):
            query = query.filter(Entry.trend == q_trend)
        if q_price_min is not None:
            query = query.filter(Entry.price >= q_price_min)
        if q_price_max is not None:
            query = query.filter(Entry.price <= q_price_max)
        if q_percent_min is not None:
            query = query.filter(Entry.percent >= q_percent_min)
        if q_percent_max is not None:
            query = query.filter(Entry.percent <= q_percent_max)
        if q_prod == "yes":
            query = query.filter(Entry.is_production_city.is_(True))
        elif q_prod == "no":
            query = query.filter(Entry.is_production_city.is_(False))

        sort_map = {
            "price_asc": Entry.price.asc(),
            "price_desc": Entry.price.desc(),
            "percent_asc": Entry.percent.asc(),
            "percent_desc": Entry.percent.desc(),
            "updated_asc": Entry.updated_at.asc().nullslast(),
            "updated_desc": Entry.updated_at.desc().nullslast(),
        }
        query = query.order_by(sort_map.get(q_sort, sort_map["updated_desc"]))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        entries = pagination.items

        window = 20
        start = max(1, pagination.page - (window // 2))
        end = min(pagination.pages, start + window - 1) if pagination.pages else 1
        start = max(1, end - window + 1)
        page_numbers = list(range(start, (end or 0) + 1)) if pagination.pages else []

        cities_list = cached_list(
            "cities",
            lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()],
        )
        products_list = cached_list(
            "products",
            lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()],
        )
        product_suggestions = _build_product_suggestions(products_list)

        total_entries = pagination.total
        total_cities = len(cities_list)
        total_products = len(products_list)

        return render_template(
            "prices.html",
            entries=entries,
            pagination=pagination,
            page_numbers=page_numbers,
            per_page=per_page,
            cities_list=cities_list,
            products_list=products_list,
            product_suggestions=product_suggestions,
            q_city=q_city,
            q_product=q_product,
            q_trend=q_trend,
            q_price_min=q_price_min,
            q_price_max=q_price_max,
            q_percent_min=q_percent_min,
            q_percent_max=q_percent_max,
            q_prod=q_prod,
            q_sort=q_sort,
            totals={
                "entries": total_entries,
                "cities": total_cities,
                "products": total_products,
            },
            lang=lang,
        )

    if tab == "dynamics":
        q_city = (request.args.get("city") or "").strip()
        q_product = (request.args.get("product") or "").strip()

        combos = (
            db.session.query(Entry.city, Entry.product)
            .distinct()
            .order_by(Entry.city.asc(), Entry.product.asc())
            .all()
        )

        city_to_products: Dict[str, Set[str]] = {}
        for city, product in combos:
            city_to_products.setdefault(city, set()).add(product)

        all_cities = sorted(city_to_products.keys(), key=str.lower)
        if not q_city and all_cities:
            q_city = all_cities[0]

        products_for_city = sorted(
            city_to_products.get(q_city, set()),
            key=str.lower,
        )
        if not q_product and products_for_city:
            q_product = products_for_city[0]
        if q_product and products_for_city and q_product not in products_for_city:
            q_product = products_for_city[0]

        timeline_query = EntrySnapshot.query
        if q_city:
            timeline_query = timeline_query.filter(EntrySnapshot.city == q_city)
        if q_product:
            timeline_query = timeline_query.filter(EntrySnapshot.product == q_product)

        timeline_entries = (
            timeline_query
            .order_by(EntrySnapshot.recorded_at.asc(), EntrySnapshot.id.asc())
            .limit(1000)
            .all()
        )

        timeline = [
            {
                "timestamp": snapshot.recorded_at.isoformat(),
                "price": snapshot.price,
                "percent": snapshot.percent,
                "trend": snapshot.trend,
            }
            for snapshot in timeline_entries
            if snapshot.recorded_at
        ]

        latest_entry = timeline_entries[-1] if timeline_entries else None
        previous_entry = timeline_entries[-2] if len(timeline_entries) > 1 else None
        latest_price = latest_entry.price if latest_entry else None
        previous_price = previous_entry.price if previous_entry else None
        delta_price = None
        delta_percent = None
        if latest_price is not None and previous_price is not None:
            delta_price = latest_price - previous_price
            if previous_price:
                delta_percent = (delta_price / previous_price) * 100

        latest_timestamp = latest_entry.recorded_at if latest_entry else None

        table_entries = timeline_entries[-100:]

        return render_template(
            "dynamics.html",
            timeline=timeline,
            city=q_city,
            product=q_product,
            all_cities=all_cities,
            products_for_city=products_for_city,
            delta_price=delta_price,
            delta_percent=delta_percent,
            latest_entry=latest_entry,
            latest_timestamp=latest_timestamp,
            points_count=len(timeline),
            timeline_entries=table_entries,
            lang=lang,
        )

    if tab == "routes":
        q_product = (request.args.get("product") or "").strip()
        q_buy_city = (request.args.get("buy_city") or "").strip()
        q_sell_city = (request.args.get("sell_city") or "").strip()
        buy_only_prod = request.args.get("buy_only_prod") in ("1", "true", "on", "yes", "y", "да")

        k = max(1, min(10, request.args.get("k", type=int) or 5))
        min_items = max(1, min(10, request.args.get("min_items", type=int) or 1))
        max_items = max(min_items, min(10, request.args.get("max_items", type=int) or 10))
        sort_by = (request.args.get("sort") or "sum_profit_desc").strip().lower()
        page = request.args.get("page", 1, type=int)
        per_page = max(1, min(100, request.args.get("per_page", 12, type=int)))

        min_profit = request.args.get("min_profit", type=float)
        min_margin = request.args.get("min_margin", type=float)
        min_buy_percent = request.args.get("min_buy_percent", type=float)
        min_sell_percent = request.args.get("min_sell_percent", type=float)
        buy_trend = (request.args.get("buy_trend") or "any").strip().lower()
        sell_trend = (request.args.get("sell_trend") or "any").strip().lower()
        max_age_value = request.args.get("max_age_value", type=int)
        max_age_unit = (request.args.get("max_age_unit") or "h").strip().lower()

        latest = latest_entries_subquery()

        products_list = cached_list(
            "products_latest",
            lambda: [p for (p,) in db.session.query(latest.c.product).distinct().order_by(latest.c.product.asc()).all()],
        )
        cities_list = cached_list(
            "cities_latest",
            lambda: [c for (c,) in db.session.query(latest.c.city).distinct().order_by(latest.c.city.asc()).all()],
        )
        product_suggestions = _build_product_suggestions(products_list)

        query = (
            db.session.query(
                latest.c.id,
                latest.c.city,
                latest.c.product,
                latest.c.price,
                latest.c.percent,
                latest.c.trend,
                latest.c.updated_at,
                latest.c.created_at,
                latest.c.is_production_city,
                latest.c.image_path,
            )
            .select_from(latest)
        )
        if q_product:
            query = query.filter(latest.c.product.ilike(f"%{q_product}%"))
        rows = query.all()
        if not rows:
            return render_template(
                "routes.html",
                groups=[],
                products_list=products_list,
                cities_list=cities_list,
                q_product=q_product,
                q_buy_city=q_buy_city,
                q_sell_city=q_sell_city,
                buy_only_prod=buy_only_prod,
                min_profit=min_profit,
                min_margin=min_margin,
                min_buy_percent=min_buy_percent,
                min_sell_percent=min_sell_percent,
                buy_trend=buy_trend,
                sell_trend=sell_trend,
                max_age_value=max_age_value,
                max_age_unit=max_age_unit,
                k=k,
                min_items=min_items,
                max_items=max_items,
                sort_by=sort_by,
                pagination=None,
                page_numbers=[],
                lang=lang,
                per_page=per_page,
                product_suggestions=product_suggestions,
            )

        from collections import defaultdict

        buy_map = defaultdict(dict)
        sell_map = defaultdict(dict)
        cities = set()
        for row in rows:
            cities.add(row.city)
            if buy_only_prod:
                if row.is_production_city:
                    buy_map[row.city].setdefault(row.product, row)
            else:
                buy_map[row.city].setdefault(row.product, row)
            sell_map[row.city].setdefault(row.product, row)

        def to_iso_utc(dt: Optional[datetime]):
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None

        groups = []
        for buy_city in cities:
            for sell_city in cities:
                if buy_city == sell_city:
                    continue
                if q_buy_city and q_buy_city.lower() not in buy_city.lower():
                    continue
                if q_sell_city and q_sell_city.lower() not in sell_city.lower():
                    continue

                common_products = set(buy_map.get(buy_city, {})) & set(sell_map.get(sell_city, {}))
                if not common_products:
                    continue

                items = []
                for product in common_products:
                    buy_entry = buy_map[buy_city][product]
                    sell_entry = sell_map[sell_city][product]
                    margin = sell_entry.price - buy_entry.price
                    percent_margin = (margin / buy_entry.price * 100) if buy_entry.price else 0
                    buy_dt = buy_entry.updated_at or buy_entry.created_at
                    sell_dt = sell_entry.updated_at or sell_entry.created_at
                    if min_profit is not None and margin < min_profit:
                        continue
                    if min_margin is not None and percent_margin < min_margin:
                        continue
                    if min_buy_percent is not None and (buy_entry.percent or 0) < min_buy_percent:
                        continue
                    if min_sell_percent is not None and (sell_entry.percent or 0) < min_sell_percent:
                        continue
                    if buy_trend in {"up", "down"} and buy_entry.trend != buy_trend:
                        continue
                    if sell_trend in {"up", "down"} and sell_entry.trend != sell_trend:
                        continue
                    if max_age_value:
                        delta = datetime.utcnow() - (sell_entry.updated_at or sell_entry.created_at)
                        multiplier = {"m": 60, "h": 3600, "d": 86400}.get(max_age_unit, 3600)
                        if delta.total_seconds() > max_age_value * multiplier:
                            continue

                    items.append(
                        {
                            "product": product,
                            "buy_city": buy_city,
                            "sell_city": sell_city,
                            "buy_price": buy_entry.price,
                            "sell_price": sell_entry.price,
                            "buy_entry_id": buy_entry.id,
                            "sell_entry_id": sell_entry.id,
                            "buy_percent": buy_entry.percent,
                            "sell_percent": sell_entry.percent,
                            "buy_trend": buy_entry.trend,
                            "sell_trend": sell_entry.trend,
                            "margin": margin,
                            "percent_margin": percent_margin,
                            "profit": margin,
                            "margin_pct": percent_margin,
                            "buy_updated_iso": to_iso_utc(buy_dt),
                            "sell_updated_iso": to_iso_utc(sell_dt),
                            "buy_updated_dt": buy_dt,
                            "sell_updated_dt": sell_dt,
                            "image_path": buy_entry.image_path or sell_entry.image_path,
                        }
                    )

                if not items:
                    continue

                items.sort(key=lambda x: x["margin"], reverse=True)
                top_items = items[:k]
                sum_profit = sum(item["margin"] for item in top_items)
                avg_margin = sum(item["percent_margin"] for item in top_items) / len(top_items)

                latest_timestamp = max(
                    [item["buy_updated_dt"] for item in top_items] +
                    [item["sell_updated_dt"] for item in top_items]
                )
                for item in top_items:
                    item.pop("buy_updated_dt", None)
                    item.pop("sell_updated_dt", None)

                groups.append(
                    {
                        "pair_from": buy_city,
                        "pair_to": sell_city,
                        "entries": top_items,
                        "items_total": len(items),
                        "sum_profit": sum_profit,
                        "avg_margin": avg_margin,
                        "updated_utc_iso": to_iso_utc(latest_timestamp),
                        "fresh_ts": latest_timestamp,
                    }
                )

        groups = [g for g in groups if min_items <= g["items_total"] <= max_items]

        sort_key = {
            "sum_profit_desc": lambda g: (-g["sum_profit"], -g["avg_margin"]),
            "avg_margin_desc": lambda g: (-g["avg_margin"], -g["sum_profit"]),
            "count_desc": lambda g: (-g["items_total"], -g["sum_profit"]),
            "fresh_desc": lambda g: (-g["fresh_ts"].timestamp(), -g["sum_profit"]),
        }.get(sort_by, lambda g: (-g["sum_profit"], -g["avg_margin"]))

        groups.sort(key=sort_key)

        total_groups = len(groups)
        total_pages = max(1, (total_groups + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_groups = groups[start_idx:end_idx]
        for grp in page_groups:
            grp.pop("fresh_ts", None)

        window = 10
        start_page = max(1, page - window // 2)
        end_page = min(total_pages, start_page + window - 1)
        start_page = max(1, end_page - window + 1)
        page_numbers = list(range(start_page, end_page + 1))

        pagination = {
            "page": page,
            "pages": total_pages,
            "total": total_groups,
            "per_page": per_page,
        }

        return render_template(
            "routes.html",
            groups=page_groups,
            products_list=products_list,
            cities_list=cities_list,
            q_product=q_product,
            q_buy_city=q_buy_city,
            q_sell_city=q_sell_city,
            buy_only_prod=buy_only_prod,
            min_profit=min_profit,
            min_margin=min_margin,
            min_buy_percent=min_buy_percent,
            min_sell_percent=min_sell_percent,
            buy_trend=buy_trend,
            sell_trend=sell_trend,
            max_age_value=max_age_value,
            max_age_unit=max_age_unit,
            k=k,
            min_items=min_items,
            max_items=max_items,
            sort_by=sort_by,
            pagination=pagination,
            page_numbers=page_numbers,
            lang=lang,
            per_page=per_page,
            product_suggestions=product_suggestions,
        )

    return redirect(url_for("index", tab="prices", lang=lang))


def new_entry():
    lang = get_lang()
    cities_list = cached_list(
        "cities",
        lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()],
    )
    products_list = cached_list(
        "products",
        lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()],
    )
    product_suggestions = _build_product_suggestions(products_list)

    if request.method == "POST":
        action = (request.form.get("_action") or "submit_request").strip()
        next_url = safe_next(request.form.get("next")) or safe_next(request.args.get("next"))

        admin_password = current_app.config.get("ADMIN_PASSWORD")
        if action in {"approve", "reject"}:
            admin_pass = request.form.get("admin_pass", "")
            if not admin_pass:
                flash(translate("required_password"))
                return redirect(url_for("new_entry", lang=lang))
            if admin_pass != admin_password:
                flash(translate("wrong_password"))
                return redirect(url_for("new_entry", lang=lang))

            pending_id = request.form.get("pending_id", type=int)
            if not pending_id:
                flash(translate("no_data"))
                return redirect(url_for("new_entry", lang=lang))

            pending = PendingEntry.query.get(pending_id)
            if not pending:
                flash(translate("no_data"))
                return redirect(url_for("new_entry", lang=lang))

            if action == "approve":
                approve_pending(pending)
                flash(translate("approved"))
            else:
                db.session.delete(pending)
                db.session.commit()
                flash(translate("rejected"))
            return redirect(url_for("new_entry", lang=lang))

        city = (request.form.get("city") or "").strip()
        product = (request.form.get("product") or "").strip()
        try:
            price = float(request.form.get("price") or 0)
        except Exception:
            price = 0.0
        trend_value = (request.form.get("trend") or "up").strip()
        try:
            percent_value = float(request.form.get("percent") or 0)
        except Exception:
            percent_value = 0.0
        is_prod = parse_bool(request.form.get("is_production_city"))

        if not city or not product:
            flash(translate("no_data"))
        else:
            existing_entry = Entry.query.filter(
                func.lower(Entry.city) == func.lower(city),
                func.lower(Entry.product) == func.lower(product),
            ).first()

            if action in {"find_existing", "submit_request"} and existing_entry:
                flash(translate("edit_existing"))
                return _redirect_to_edit(
                    existing_entry.id,
                    lang,
                    next_url=next_url,
                    price=price or None,
                    percent=percent_value or None,
                    trend=trend_value or None,
                )

            if action == "submit_request":
                if price <= 0:
                    flash(translate("no_data"))
                else:
                    pending = PendingEntry(
                        city=city,
                        product=product,
                        price=price,
                        trend=trend_value,
                        percent=percent_value,
                        is_production_city=is_prod,
                        submit_ip=request.remote_addr,
                    )
                    db.session.add(pending)
                    db.session.commit()
                    flash(translate("request_submitted"))

    pending = PendingEntry.query.order_by(PendingEntry.submitted_at.desc()).all()
    return render_template(
        "entry_form.html",
        e=None,
        title=translate("new_entry"),
        cities_list=cities_list,
        products_list=products_list,
        product_suggestions=product_suggestions,
        pending=pending,
        next_url=request.args.get("next"),
    )


def edit_entry(entry_id: int):
    lang = get_lang()
    entry = Entry.query.get_or_404(entry_id)

    if request.method == "POST":
        next_param = request.form.get("next")
        safe_next_value = safe_next(next_param)
        redirect_args = {"entry_id": entry.id, "lang": lang}
        if safe_next_value:
            redirect_args["next"] = safe_next_value

        action = (request.form.get("_action") or "save").strip()

        if action == "delete":
            admin_password = current_app.config.get("ADMIN_PASSWORD")
            admin_pass = request.form.get("admin_pass", "")
            if not admin_pass:
                flash(translate("required_password"))
                return redirect(url_for("edit_entry", **redirect_args))
            if admin_pass != admin_password:
                flash(translate("wrong_password"))
                return redirect(url_for("edit_entry", **redirect_args))

            image_path = entry.image_path
            db.session.delete(entry)
            db.session.commit()
            flash(translate("deleted"))

            if image_path:
                still_used = (
                    db.session.query(Entry.id)
                    .filter(Entry.image_path == image_path)
                    .first()
                )
                if not still_used:
                    _delete_image_file(image_path)

            invalidate_product_image_cache()

            next_url = safe_next_value or url_for("index", lang=lang)
            return redirect(next_url)

        image_file = request.files.get("image")
        new_image_path: Optional[str] = None
        if image_file and image_file.filename:
            try:
                new_image_path = _save_entry_image(image_file)
            except ValueError:
                flash(translate("invalid_image"))
                return redirect(url_for("edit_entry", **redirect_args))

        previous_image_path = entry.image_path
        invalidate_cache = False
        try:
            entry.price = float(request.form.get("price", entry.price))
        except Exception:
            pass
        entry.trend = (request.form.get("trend") or entry.trend).strip()
        try:
            entry.percent = float(request.form.get("percent", entry.percent))
        except Exception:
            pass
        entry.is_production_city = parse_bool(
            request.form.get("is_production_city", entry.is_production_city)
        )
        if new_image_path:
            entry.image_path = new_image_path
            invalidate_cache = True
            # propagate the new image to every entry of the same product so
            # all cities stay in sync without touching their update timestamps
            db.session.execute(
                sa.update(Entry)
                .where(func.lower(Entry.product) == func.lower(entry.product))
                .where(Entry.id != entry.id)
                .values(image_path=new_image_path, updated_at=Entry.updated_at)
            )
        db.session.flush()
        record_snapshot(entry)
        db.session.commit()
        flash(translate("updated"))
        dedupe_entries()
        if new_image_path and previous_image_path and previous_image_path != new_image_path:
            still_used = (
                db.session.query(Entry.id)
                .filter(Entry.image_path == previous_image_path)
                .first()
            )
            if not still_used:
                _delete_image_file(previous_image_path)
                invalidate_cache = True
        if invalidate_cache:
            invalidate_product_image_cache()
        next_url = next_param or url_for("index", lang=lang)
        return redirect(next_url)

    overrides = {
        "price": request.args.get("price") if request.args.get("price") is not None else None,
        "percent": request.args.get("percent") if request.args.get("percent") is not None else None,
        "trend": request.args.get("trend") if request.args.get("trend") is not None else None,
    }

    cities_list = cached_list(
        "cities",
        lambda: [c for (c,) in db.session.query(Entry.city).distinct().order_by(Entry.city.asc()).all()],
    )
    products_list = cached_list(
        "products",
        lambda: [p for (p,) in db.session.query(Entry.product).distinct().order_by(Entry.product.asc()).all()],
    )
    next_url = safe_next(request.args.get("next")) or safe_next(request.referrer)
    product_suggestions = _build_product_suggestions(products_list)

    return render_template(
        "entry_form.html",
        e=entry,
        title=translate("edit_entry"),
        cities_list=cities_list,
        products_list=products_list,
        next_url=next_url,
        overrides=overrides,
        product_suggestions=product_suggestions,
    )



def import_csv():
    lang = get_lang()
    if request.method == "POST":
        admin_password = current_app.config.get("ADMIN_PASSWORD")
        admin_pass = request.form.get("admin_pass", "")
        if not admin_pass:
            flash(translate("required_password"))
            return redirect(url_for("import_csv", lang=lang))
        if admin_pass != admin_password:
            flash(translate("wrong_password"))
            return redirect(url_for("import_csv", lang=lang))
        file = request.files.get("file")
        if not file:
            flash("No file provided")
            return redirect(url_for("import_csv", lang=lang))

        textbuf = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(textbuf))
        count = 0
        for row in reader:
            try:
                created_at_str = row.get("created_at")
                created_at = (
                    datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if created_at_str
                    else datetime.utcnow()
                )
                city = row.get("city", "").strip()
                product = row.get("product", "").strip()
                price = float(row.get("price"))
                trend_value = (row.get("trend") or "up").strip()
                percent_value = float(row.get("percent") or 0)
                is_prod = parse_bool(row.get("is_production_city"))
                existing = Entry.query.filter_by(city=city, product=product).first()
                if existing:
                    existing.price = price
                    existing.trend = trend_value
                    existing.percent = percent_value
                    existing.is_production_city = existing.is_production_city or is_prod
                    existing.created_at = existing.created_at or created_at
                    db.session.flush()
                    record_snapshot(existing, recorded_at=created_at)
                else:
                    new_entry = Entry(
                        created_at=created_at,
                        city=city,
                        product=product,
                        price=price,
                        trend=trend_value,
                        percent=percent_value,
                        is_production_city=is_prod,
                    )
                    db.session.add(new_entry)
                    db.session.flush()
                    record_snapshot(new_entry, recorded_at=created_at)
                count += 1
            except Exception as exc:
                current_app.logger.warning("Import error: %s", exc)
                db.session.rollback()
        db.session.commit()
        dedupe_entries()
        flash(translate("imported").format(n=count))
        next_url = request.form.get("next") or url_for("index", lang=lang)
        return redirect(next_url)
    return render_template("import_form.html")


def export_csv():
    q_city = (request.args.get("city") or "").strip()
    q_product = (request.args.get("product") or "").strip()
    q_trend = (request.args.get("trend") or "").strip()
    q_from = (request.args.get("from") or "").strip()
    q_to = (request.args.get("to") or "").strip()

    query = Entry.query
    if q_city:
        query = query.filter(Entry.city.ilike(f"%{q_city}%"))
    if q_product:
        query = query.filter(Entry.product.ilike(f"%{q_product}%"))
    if q_trend in ("up", "down"):
        query = query.filter(Entry.trend == q_trend)

    def parse_dt(value: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            try:
                return datetime.fromisoformat(value + "T00:00:00")
            except Exception:
                return None

    dt_from = parse_dt(q_from) if q_from else None
    dt_to = parse_dt(q_to) if q_to else None
    if dt_from:
        query = query.filter(Entry.created_at >= dt_from)
    if dt_to:
        query = query.filter(Entry.created_at <= dt_to)

    rows = query.order_by(Entry.created_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "created_at",
            "updated_at",
            "city",
            "product",
            "price",
            "trend",
            "percent",
            "is_production_city",
        ]
    )
    for entry in rows:
        writer.writerow(
            [
                entry.id,
                entry.created_at.isoformat(),
                (entry.updated_at or entry.created_at).isoformat(),
                entry.city,
                entry.product,
                f"{entry.price:.0f}",
                entry.trend,
                f"{entry.percent:.0f}",
                "true" if entry.is_production_city else "false",
            ]
        )
    resp = Response(buf.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = "attachment; filename=entries.csv"
    return resp


def admin_dedupe():
    dedupe_entries()
    flash("Deduplicated")
    return redirect(url_for("index", lang=get_lang()))


def health():
    return {"status": "ok"}


def not_found(error):  # pragma: no cover - delegated to Flask
    return render_template("404.html"), 404


def internal_error(error):  # pragma: no cover - delegated to Flask
    db.session.rollback()
    return render_template("500.html"), 500
