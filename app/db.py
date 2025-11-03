# app/db.py
import os
import psycopg2
import psycopg2.pool
import psycopg2.extras

_pool = None
_dsn = None

def init_db_pool(database_url: str):
    """Создаёт пул соединений (если ещё не создан)."""
    global _pool, _dsn
    if _pool is not None:
        return
    _dsn = database_url
    try:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("DB_MAX_CONN", "10")),
            dsn=_dsn,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        print("[DB] Pool initialized")
    except Exception as e:
        _pool = None
        print("[DB] Pool init failed:", e)

def close_db_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None

def _ensure_pool():
    if _pool is None:
        from .config import Config
        init_db_pool(Config.DATABASE_URL)
    if _pool is None:
        raise RuntimeError("DB pool not initialized: check DATABASE_URL and sslmode=require on Railway")

def _get_conn():
    _ensure_pool()
    return _pool.getconn()

def _put_conn(conn):
    if _pool:
        _pool.putconn(conn)

def query(sql: str, params: tuple = ()):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        _put_conn(conn)

def one(sql: str, params: tuple = ()):
    rows = query(sql, params)
    return rows[0] if rows else None

def execute(sql: str, params: tuple = ()):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    finally:
        _put_conn(conn)
