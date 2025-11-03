# app/config.py
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def _get_db_url():
    raw = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRESQL_URL")
        or os.getenv("RAILWAY_DATABASE_URL")
        or "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    # добавим sslmode=require для удалённого хоста
    try:
        u = urlparse(raw)
        host_is_local = (u.hostname in {"localhost", "127.0.0.1"})
        if not host_is_local:
            q = parse_qs(u.query)
            if "sslmode" not in q:
                q["sslmode"] = ["require"]
                raw = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))
    except Exception:
        pass
    return raw

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    DATABASE_URL = _get_db_url()
