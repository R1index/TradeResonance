from app import create_app

def create_app():
    return _create()

def _create():
    return create_app()

app = create_app()  # ✅ нужно, чтобы gunicorn нашёл "app"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
