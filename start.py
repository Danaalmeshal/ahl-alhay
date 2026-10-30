"""Start script for Render: prepare the database on first run, then start the web server."""
import os
import sys

from app import app
import db


def ensure_db():
    """Create the tables and demo data if the database does not exist yet."""
    path = app.config["DATABASE"]
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with app.app_context():
            db.init_db()
        print("Database created with demo neighborhoods and administrators.")


def main():
    ensure_db()
    port = os.environ.get("PORT", "10000")
    os.execvp(sys.executable, [
        sys.executable, "-m", "gunicorn", "app:app",
        "--bind", f"0.0.0.0:{port}", "--workers", "1", "--threads", "4",
    ])


if __name__ == "__main__":
    main()
