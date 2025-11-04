
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from sqlalchemy import select, func, text
from ..extensions import db
from ..models import Entry

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    # Pagination
    page = max(int(request.args.get('page', 1)), 1)
    per_page = min(max(int(request.args.get('per_page', 50)), 1), 200)

    q = Entry.query.order_by(Entry.updated_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('index.html', pagination=pagination, items=pagination.items)

@bp.route('/export.csv')
def export_csv():
    # Stream CSV of latest unique (city, product)
    # Postgres DISTINCT ON fallback: for SQLite, select max(updated_at) per pair
    engine_name = db.engine.name
    if engine_name == 'postgresql':
        sql = text("""
            SELECT DISTINCT ON (city, product)
                   city, product, price, created_at, updated_at
            FROM entries
            ORDER BY city, product, updated_at DESC
        """)
        rows = db.session.execute(sql).all()
    else:
        sub = db.session.query(
            Entry.city, Entry.product, func.max(Entry.updated_at).label('mx')
        ).group_by(Entry.city, Entry.product).subquery()
        rows = db.session.query(Entry).join(
            sub, (Entry.city==sub.c.city) & (Entry.product==sub.c.product) & (Entry.updated_at==sub.c.mx)
        ).all()

    def gen():
        yield "city,product,price,created_at,updated_at\n"
        for r in rows:
            if hasattr(r, 'city'):
                yield f"{r.city},{r.product},{r.price},{r.created_at},{r.updated_at}\n"
            else:
                c,p,price,cr,up = r
                yield f"{c},{p},{price},{cr},{up}\n"
    return Response(gen(), mimetype='text/csv')
