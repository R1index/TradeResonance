# Trade Resonance

Modernised Flask + HTMX interface for tracking trade data in Resonance Solstice.

## Highlights

- Fresh responsive shell built with Tailwind, theme toggling and mobile drawer.
- HTMX-powered dashboard with live filters for prices, city breakdowns and trade routes.
- English and Russian localisation baked in, including flash-toasts rendered client side.
- CSV import/export, duplicate cleanup and admin approvals handled from the UI.
- Database helpers centralised in `traderesonance/services/entries.py` with caching and pagination.

## Run
```bash
pip install -r requirements.txt
export SECRET_KEY=dev; export DATABASE_URL=sqlite:///local.db; export PORT=8080
python app.py
```

## Railway
- Set `DATABASE_URL` from Postgres plugin; `Procfile` already provided.
