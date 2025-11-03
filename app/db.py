import os
import psycopg2
import psycopg2.pool
import psycopg2.extras

_pool = None

def init_db_pool(database_url: str):
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("DB_MAX_CONN", "10")),
            dsn=database_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )

def close_db_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None

def _get_conn():
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
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
