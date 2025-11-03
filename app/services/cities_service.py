from ..db import query
# TODO: вынесите в отдельные таблицы, если они у вас есть
# Временно читаем из prices

def city_list() -> list[str]:
    rows = query("SELECT DISTINCT city FROM prices ORDER BY city")
    return [r["city"] for r in rows]
