"""WSGI entry-point for Trade Resonance."""
from __future__ import annotations

from traderesonance import create_app

app = create_app()


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
