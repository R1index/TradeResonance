from ..db import query

def product_list() -> list[str]:
    rows = query("SELECT DISTINCT product FROM prices ORDER BY product")
    return [r["product"] for r in rows]
