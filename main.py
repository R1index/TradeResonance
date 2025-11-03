import os
from app import create_app as _create_app  # берем фабрику из app/__init__.py

app = _create_app()  # создаем WSGI-приложение для gunicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
