# Trade Helper (Flask + PostgreSQL) for Railway

Minimal web app to crowdsource city prices in the game **Resonance Solstice** and compute profitable trade routes.

## Features
- Add/edit entries: city, product, price, trend (up/down), percent, production city flag
- EN + RU localization (toggle in navbar)
- Prices list, Cities overview (produces + avg price), Profitable routes (per product: best buy/sell, spread, profit)
- CSV import (`/import`)
- Healthcheck `/health`

## Tech
- Flask, SQLAlchemy, Flask-SQLAlchemy
- PostgreSQL on Railway (uses `DATABASE_URL`); works with SQLite locally
- Bootstrap 5 (CDN)

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY=dev; export DATABASE_URL=sqlite:///local.db; export PORT=8080
python app.py
# open http://localhost:8080/
```

## Deploy on Railway
1. Create a new project (Deploy from GitHub) and push this repository.
2. Add a **PostgreSQL** database (plugin) to the project.
3. In **Variables**, set:
   - `SECRET_KEY` — any random string
   - `DATABASE_URL` — Railway will provide it (or keep from plugin)
4. Deploy; `Procfile` runs: `web: gunicorn app:app --preload --workers=2 --threads=4 --timeout=120`

## CSV format
Expected columns: `id (optional)`, `created_at (optional ISO)`, `city`, `product`, `price`, `trend`, `percent`, `is_production_city`.

```
city,product,price,trend,percent,is_production_city,created_at
Aurora,Iron Ore,120,up,5,true,2025-11-01T12:00:00Z
```


## New
- City overview now shows ONLY products produced in that city (production flag).
- Autocomplete for city & product fields (datalist).
- Filters on Prices tab (city, product, trend, date range).
- Created/Updated timestamps shown.
