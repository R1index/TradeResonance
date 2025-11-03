# Простейший "DAO-слой" через SQL (если не используете ORM).
# В реальном проекте можно вынести DDL/миграции и использовать Alembic/SQLAlchemy.

PRICE_COLUMNS = ["id", "city", "product", "price", "created_at"]

SQL_ALL_PRICES = "SELECT id, city, product, price, created_at FROM prices ORDER BY created_at DESC LIMIT %s OFFSET %s"
SQL_INSERT_PRICE = "INSERT INTO prices (city, product, price) VALUES (%s, %s, %s)"
SQL_DELETE_PRICE = "DELETE FROM prices WHERE id = %s"

SQL_DISTINCT_CITIES = "SELECT DISTINCT city FROM prices ORDER BY city"
SQL_DISTINCT_PRODUCTS = "SELECT DISTINCT product FROM prices ORDER BY product"

# TODO: Добавьте ваши таблицы/представления/вьюхи и актуальные колонки
