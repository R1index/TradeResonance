# Trade Helper (Flask + Postgres) — Tailwind UI + Deduplication
- One row per (city, product): dedupe on startup and on import/create; unique index.
- EN/RU, responsive UI, dark/light theme, toasts, routes, cities accordion, filters.

## Run
```bash
pip install -r requirements.txt
export SECRET_KEY=dev; export DATABASE_URL=sqlite:///local.db; export PORT=8080
python app.py
```

## Railway
- Set `DATABASE_URL` from Postgres plugin; `Procfile` already provided.
