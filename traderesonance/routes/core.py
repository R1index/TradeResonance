"""HTTP route declarations for the Trade Resonance web UI."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.exceptions import NotFound

from sqlalchemy import func

from ..extensions import db
from ..localization import context_processor, get_lang, translate
from ..models import Entry, PendingEntry
from ..services.entries import (
    CityFilters,
    PriceFilters,
    RouteFilters,
    approve_pending,
    cached_list,
    create_pending,
    dedupe_entries,
    export_rows,
    fetch_city_groups,
    fetch_price_page,
    fetch_route_page,
    import_rows,
)
from ..utils import parse_bool, safe_next

bp = Blueprint("web", __name__)


# ---------------------------------------------------------------------------
# Blueprint registration
# ---------------------------------------------------------------------------


def register(app) -> None:
    app.context_processor(context_processor)
    app.register_blueprint(bp)
    app.add_url_rule("/health", view_func=health)
    app.register_error_handler(404, not_found)
    app.register_error_handler(500, internal_error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lists_for_forms() -> Tuple[List[str], List[str]]:
    cities = cached_list(
        "cities",
        lambda: [
            c
            for (c,) in db.session.query(Entry.city)
            .distinct()
            .order_by(Entry.city.asc())
            .all()
        ],
    )
    products = cached_list(
        "products",
        lambda: [
            p
            for (p,) in db.session.query(Entry.product)
            .distinct()
            .order_by(Entry.product.asc())
            .all()
        ],
    )
    return cities, products


def _resolve_tab(tab: str, lang: str) -> Tuple[str, Dict[str, object]]:
    tab = tab or "prices"
    if tab == "prices":
        filters = PriceFilters.from_args(request.args)
        page = request.args.get("page", default=1, type=int) or 1
        per_page = request.args.get("per_page", default=15, type=int) or 15
        price_page = fetch_price_page(filters, page=page, per_page=per_page)
        cities_list, products_list = _lists_for_forms()
        export_args = request.args.to_dict(flat=True)
        export_args.pop("tab", None)
        export_args["lang"] = lang
        export_url = url_for(
            "web.export_csv",
            **{k: v for k, v in export_args.items() if v not in (None, "")},
        )
        return (
            "partials/prices.html",
            {
                "filters": filters,
                "price_page": price_page,
                "cities_list": cities_list,
                "products_list": products_list,
                "export_url": export_url,
                "lang": lang,
                "tab": tab,
            },
        )

    if tab == "cities":
        filters = CityFilters.from_args(request.args)
        groups = fetch_city_groups(filters)
        return (
            "partials/cities.html",
            {
                "filters": filters,
                "groups": groups,
                "lang": lang,
                "tab": tab,
            },
        )

    if tab == "routes":
        filters = RouteFilters.from_args(request.args)
        route_page = fetch_route_page(filters)
        cities_list, products_list = _lists_for_forms()
        return (
            "partials/routes.html",
            {
                "filters": filters,
                "route_page": route_page,
                "cities_list": cities_list,
                "products_list": products_list,
                "lang": lang,
                "tab": tab,
            },
        )

    raise NotFound()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@bp.get("/")
def dashboard():
    lang = get_lang()
    tab = request.args.get("tab", "prices")
    template, context = _resolve_tab(tab, lang)
    context.setdefault("lang", lang)
    context.setdefault("tab", tab)

    if request.headers.get("HX-Request"):
        return render_template(template, **context)

    return render_template("home.html", tab_template=template, **context)


@bp.get("/tabs/<tab>")
def tab_partial(tab: str):
    lang = get_lang()
    template, context = _resolve_tab(tab, lang)
    context.setdefault("lang", lang)
    context.setdefault("tab", tab)
    return render_template(template, **context)


@bp.route("/entries/new", methods=["GET", "POST"])
def new_entry():
    lang = get_lang()
    cities_list, products_list = _lists_for_forms()

    if request.method == "POST":
        action = (request.form.get("_action") or "submit").strip().lower()
        next_url = safe_next(request.form.get("next"))

        admin_password = current_app.config.get("ADMIN_PASSWORD")
        if action in {"approve", "reject"}:
            admin_pass = request.form.get("admin_pass", "")
            if not admin_pass:
                flash(translate("required_password"))
                return redirect(url_for("web.new_entry", lang=lang))
            if admin_pass != admin_password:
                flash(translate("wrong_password"))
                return redirect(url_for("web.new_entry", lang=lang))
            pending_id = request.form.get("pending_id", type=int)
            pending = PendingEntry.query.get_or_404(pending_id)
            if action == "approve":
                approve_pending(pending)
                flash(translate("approved"))
            else:
                db.session.delete(pending)
                db.session.commit()
                flash(translate("rejected"))
            return redirect(url_for("web.new_entry", lang=lang))

        city = (request.form.get("city") or "").strip()
        product = (request.form.get("product") or "").strip()
        price = request.form.get("price", type=float) or 0.0
        trend = (request.form.get("trend") or "up").strip()
        percent = request.form.get("percent", type=float) or 0.0
        is_prod = parse_bool(request.form.get("is_production_city"))

        if not city or not product or price <= 0:
            flash(translate("no_data"))
            return redirect(url_for("web.new_entry", lang=lang))

        existing = Entry.query.filter(
            func.lower(Entry.city) == city.lower(),
            func.lower(Entry.product) == product.lower(),
        ).first()
        if existing:
            flash(translate("edit_existing"))
            return redirect(
                url_for(
                    "web.edit_entry",
                    entry_id=existing.id,
                    lang=lang,
                    next=next_url or url_for("web.dashboard", lang=lang),
                )
            )

        create_pending(
            city=city,
            product=product,
            price=price,
            trend=trend,
            percent=percent,
            is_production_city=is_prod,
            submit_ip=request.remote_addr,
        )
        flash(translate("request_submitted"))
        return redirect(next_url or url_for("web.dashboard", lang=lang))

    pending = PendingEntry.query.order_by(PendingEntry.submitted_at.desc()).all()
    return render_template(
        "forms/entry_form.html",
        lang=lang,
        cities_list=cities_list,
        products_list=products_list,
        pending=pending,
        next_url=safe_next(request.args.get("next")),
    )


@bp.route("/entries/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_entry(entry_id: int):
    lang = get_lang()
    entry = Entry.query.get_or_404(entry_id)
    cities_list, products_list = _lists_for_forms()

    if request.method == "POST":
        payload = {
            "price": request.form.get("price", type=float) or entry.price,
            "trend": (request.form.get("trend") or entry.trend).strip(),
            "percent": request.form.get("percent", type=float) or entry.percent,
            "is_production_city": parse_bool(
                request.form.get("is_production_city", entry.is_production_city)
            ),
        }
        entry.price = float(payload["price"])
        entry.trend = payload["trend"]
        entry.percent = float(payload["percent"])
        entry.is_production_city = bool(payload["is_production_city"])
        db.session.commit()
        dedupe_entries()
        flash(translate("updated"))
        next_url = safe_next(request.form.get("next")) or url_for("web.dashboard", lang=lang)
        return redirect(next_url)

    overrides = {
        "price": request.args.get("price"),
        "percent": request.args.get("percent"),
        "trend": request.args.get("trend"),
    }

    return render_template(
        "forms/entry_form.html",
        lang=lang,
        entry=entry,
        cities_list=cities_list,
        products_list=products_list,
        overrides=overrides,
        next_url=safe_next(request.args.get("next")) or safe_next(request.referrer),
    )


@bp.route("/import", methods=["GET", "POST"])
def import_csv():
    lang = get_lang()
    if request.method == "POST":
        admin_password = current_app.config.get("ADMIN_PASSWORD")
        admin_pass = request.form.get("admin_pass", "")
        if not admin_pass:
            flash(translate("required_password"))
            return redirect(url_for("web.import_csv", lang=lang))
        if admin_pass != admin_password:
            flash(translate("wrong_password"))
            return redirect(url_for("web.import_csv", lang=lang))

        file = request.files.get("file")
        if not file:
            flash(translate("no_data"))
            return redirect(url_for("web.import_csv", lang=lang))

        try:
            textbuf = io.StringIO(file.read().decode("utf-8"))
        except UnicodeDecodeError:
            flash("Unsupported encoding")
            return redirect(url_for("web.import_csv", lang=lang))

        reader = csv.DictReader(textbuf)
        count = import_rows(reader)
        flash(translate("imported").format(n=count))
        next_url = safe_next(request.form.get("next")) or url_for("web.dashboard", lang=lang)
        return redirect(next_url)

    return render_template("forms/import_form.html", lang=lang)


@bp.get("/export.csv")
def export_csv():
    filters = PriceFilters.from_args(request.args)

    def parse_dt(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(f"{value}T00:00:00")
            except ValueError:
                return None

    created_from = parse_dt(request.args.get("from"))
    created_to = parse_dt(request.args.get("to"))
    rows = export_rows(filters, created_from=created_from, created_to=created_to)

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
                (entry.created_at or datetime.utcnow()).isoformat(),
                (entry.updated_at or entry.created_at or datetime.utcnow()).isoformat(),
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


@bp.post("/admin/dedupe")
def admin_dedupe():
    admin_password = current_app.config.get("ADMIN_PASSWORD")
    admin_pass = request.form.get("admin_pass", "")
    if not admin_pass or admin_pass != admin_password:
        flash(translate("wrong_password"))
        return redirect(url_for("web.dashboard", lang=get_lang()))
    dedupe_entries()
    flash(translate("dedupe"))
    return redirect(url_for("web.dashboard", lang=get_lang()))


def not_found(error):  # pragma: no cover - Flask handler signature
    return render_template("errors/404.html"), 404


def internal_error(error):  # pragma: no cover - Flask handler signature
    current_app.logger.exception("Application error: %%s", error)
    return render_template("errors/500.html"), 500


def health():
    return {"status": "ok"}


__all__ = ["register"]
