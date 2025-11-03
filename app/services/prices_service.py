from typing import List, Dict, Any
from ..db import query, execute
from .. import models

def list_prices(limit:int=50, offset:int=0) -> List[Dict[str, Any]]:
    return query(models.SQL_ALL_PRICES, (limit, offset))

def create_price(city:str, product:str, price:float) -> None:
    # TODO: валидация/нормализация
    execute(models.SQL_INSERT_PRICE, (city, product, price))

def delete_price(price_id:int) -> int:
    return execute(models.SQL_DELETE_PRICE, (price_id,))

def cities() -> List[str]:
    rows = query(models.SQL_DISTINCT_CITIES)
    return [r["city"] for r in rows]

def products() -> List[str]:
    rows = query(models.SQL_DISTINCT_PRODUCTS)
    return [r["product"] for r in rows]
