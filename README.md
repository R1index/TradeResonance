
# TradeResonance (Fixed TestV8V2)

Готовый минимальный репозиторий с исправлениями:
- Рабочий submit обычной **заявки** (`_action=submit_request`) в `/entries/new`
- Автопереход на `/entries/<id>/edit` при существующей паре (city, product) с **прокидкой price/percent/trend** через query-параметры
- Умное автодополнение `<datalist>` (приоритет по префиксу) для city/product
- Сохранение `lang` и `next` во всех редиректах
- Уникальный индекс `uq_city_product` и удаление дублей на старте
- Простая i18n (`en`/`ru`) через `t()`

## Локальный запуск
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# http://localhost:5000/?lang=ru
```

## Railway
Env vars:
- `DATABASE_URL` (Postgres)
- `SECRET_KEY`

Procfile уже настроен:
```
web: gunicorn -w 2 -b 0.0.0.0:$PORT app:app
```

## Модели
- `Entry(id, city, product, price, percent, trend, is_production_city)`
- `EntryRequest(id, city, product, price, percent, trend, status)`

## Примечания
- Для реального проекта перенесите модели в отдельный модуль, добавьте миграции (Alembic).
