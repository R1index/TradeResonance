
# TradeResonance — Optimized

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export CREATE_TABLES_ON_START=1
flask --app wsgi run
```

## Env
- `DATABASE_URL` — e.g. `postgresql+psycopg://user:pass@host:5432/db`
- `SECRET_KEY` — set in prod
- `ADMIN_PASSWORD` — required to call `/admin/dedupe?token=...`

## Admin
- Dedupe: `GET /admin/dedupe?token=$ADMIN_PASSWORD`
- Health: `GET /healthz`

## Export CSV
- `GET /export.csv` — returns latest unique rows per (city, product)
