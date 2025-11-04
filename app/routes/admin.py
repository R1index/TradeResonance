
import os
from flask import Blueprint, request, redirect, url_for, flash
from sqlalchemy import text
from ..extensions import db

bp = Blueprint('admin', __name__, url_prefix='/admin')

def _check_admin():
    pwd = os.environ.get('ADMIN_PASSWORD')
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    if not pwd or token != pwd:
        return False
    return True

@bp.route('/dedupe')
def dedupe():
    if not _check_admin():
        flash('Unauthorized', 'error')
        return redirect(url_for('main.index'))

    engine_name = db.engine.name
    deleted = 0
    if engine_name == 'postgresql':
        # Delete older duplicates keeping the most recent updated_at
        sql = text("""
            DELETE FROM entries e
            USING entries e2
            WHERE e.city = e2.city
              AND e.product = e2.product
              AND e.updated_at < e2.updated_at
        """)
        result = db.session.execute(sql)
        deleted = result.rowcount or 0
    else:
        # Generic dedupe: keep max(updated_at) per pair
        sql = text("""
            DELETE FROM entries
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id FROM entries e
                    WHERE updated_at = (
                        SELECT MAX(updated_at) FROM entries i
                        WHERE i.city=e.city AND i.product=e.product
                    )
                )
            )
        """)
        result = db.session.execute(sql)
        deleted = result.rowcount or 0

    db.session.commit()
    flash(f'Deduplicated, removed {deleted} rows', 'success')
    return redirect(url_for('main.index'))
