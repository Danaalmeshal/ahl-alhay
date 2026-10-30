"""Neighborhood members page (with activity status) and the activity heartbeat."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, render_template

from db import get_db
from security import ACTIVE_WINDOW_SECONDS, login_required

bp = Blueprint("community", __name__)


def _is_active(last_seen):
    if not last_seen:
        return False
    seen = datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - seen <= timedelta(seconds=ACTIVE_WINDOW_SECONDS)


@bp.route("/neighbors")
@login_required
def neighbors():
    db = get_db()
    users = db.execute(
        "SELECT id, name, role, last_seen, created_at FROM users WHERE neighborhood_id = ?",
        (g.user["neighborhood_id"],),
    ).fetchall()
    open_requests = {}
    for r in db.execute(
        "SELECT id, title, category, author_id FROM help_requests WHERE neighborhood_id = ? AND status = 'open' "
        "ORDER BY created_at DESC, id DESC",
        (g.user["neighborhood_id"],),
    ):
        open_requests.setdefault(r["author_id"], []).append(r)
    members = [
        {"id": u["id"], "name": u["name"], "role": u["role"], "active": _is_active(u["last_seen"]),
         "requests": open_requests.get(u["id"], [])}
        for u in users
    ]
    # Omda first, then active neighbors, then by name.
    members.sort(key=lambda m: (m["role"] != "admin", not m["active"], m["name"]))
    active_count = sum(m["active"] for m in members)
    return render_template("neighbors.html", members=members, active_count=active_count)


@bp.route("/ping", methods=("POST",))
@login_required
def ping():
    """Called every minute by open pages so the user stays "active" (last_seen is updated on every request)."""
    return jsonify(ok=True)
