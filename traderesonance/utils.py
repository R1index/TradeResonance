"""Generic helpers."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from flask import request


TRUTHY = {"1", "true", "on", "yes", "y", "да"}


def safe_next(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    host = request.host.split(":")[0]
    if parsed.netloc and parsed.netloc.split(":")[0] != host:
        return None
    return url


def parse_bool(value: Optional[str]) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in TRUTHY
