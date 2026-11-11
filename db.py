"""Database connection and setup (Setup task: database tables and seed data)."""
import os
import sqlite3

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

# Demo data: two neighborhoods, each with its own administrator (Omda).
SEED_NEIGHBORHOODS = ["الملقا", "الياسمين"]
SEED_ADMINS = [
    # (name, phone, password, neighborhood)
    ("عمدة حي الملقا", "0500000001", "Omda@123", "الملقا"),
    ("عمدة حي الياسمين", "0500000002", "Omda@123", "الياسمين"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    for name in SEED_NEIGHBORHOODS:
        db.execute("INSERT INTO neighborhoods (name) VALUES (?)", (name,))
    for name, phone, password, hood in SEED_ADMINS:
        hood_id = db.execute("SELECT id FROM neighborhoods WHERE name = ?", (hood,)).fetchone()["id"]
        db.execute(
            "INSERT INTO users (name, phone, password_hash, role, neighborhood_id) VALUES (?, ?, ?, 'admin', ?)",
            (name, phone, generate_password_hash(password), hood_id),
        )
    db.commit()


@click.command("init-db")
def init_db_command():
    """Create the tables and add the demo data (deletes existing data)."""
    init_db()
    click.echo("Database created with demo neighborhoods and administrators.")


def upgrade_db():
    """Add columns/tables introduced after the first version, without losing existing data."""
    db = get_db()
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "users" not in tables:
        return  # database not created yet: run `flask --app app init-db`
    cols = {r[1] for r in db.execute("PRAGMA table_info(users)")}
    if "last_seen" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    if "notifications" not in tables:
        db.executescript(
            "CREATE TABLE notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id), "
            "kind TEXT NOT NULL, params TEXT NOT NULL DEFAULT '{}', link TEXT, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, read_at TEXT);"
        )
    # ---- Sprint 2 ----
    for table in ("help_requests", "replies"):
        if "hidden" not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
    if "notices" not in tables:
        schema = open(os.path.join(current_app.root_path, "schema.sql"), encoding="utf-8").read()
        sprint2 = schema[schema.index("-- Sprint 2, PBI 11-14"):]
        db.executescript(sprint2)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    with app.app_context():
        if os.path.exists(app.config["DATABASE"]):
            upgrade_db()
