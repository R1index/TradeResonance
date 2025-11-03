from app import create_app

# Gunicorn entrypoint: gunicorn -w 2 -b 0.0.0.0:${PORT} 'main:create_app()'
def create_app():
    return _create()

# Flask CLI entry: flask --app main run
def _create():
    return create_app()

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
