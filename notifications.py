"""Bell notifications: creating them, reading them and marking them as read."""
import json

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from db import get_db
from i18n import _
from security import login_required

bp = Blueprint("notifications", __name__, url_prefix="/notifications")

# Message templates per kind: Arabic text (translated to English by i18n when needed).
TEXTS = {
    "welcome": "مرحباً بك في حي {hood}! يمكنك الآن طلب المساعدة أو مساعدة جيرانك.",
    "new_join_request": "طلب انضمام جديد من {name}.",
    "new_help_request": "{name} نشر طلب مساعدة: {title}",
    "new_reply": "{name} ردّ على طلبك: {title}",
    "owner_reply": "{name} ردّ في الطلب: {title}",
    "request_resolved": "تم حل الطلب «{title}». شكراً لمساعدتك!",
    "new_notice": "{name} نشر بلاغاً في الحي ({category}): {location}",
    "notice_reply": "{name} ردّ على بلاغك ({category}).",
    "notice_resolved": "تم حل البلاغ ({category}). شكراً لمتابعتك!",
    "post_comment": "{name} علّق على منشورك: {title}",
    "new_report": "بلاغ جديد على محتوى ينتظر مراجعتك.",
    "content_removed": "تمت إزالة محتواك من قبل عمدة الحي بعد مراجعة بلاغ عليه.",
}


def notify(user_ids, kind, link=None, **params):
    """Create the same notification for one or more users (call db.commit() afterwards)."""
    if isinstance(user_ids, int):
        user_ids = [user_ids]
    db = get_db()
    for uid in set(user_ids):
        db.execute(
            "INSERT INTO notifications (user_id, kind, params, link) VALUES (?, ?, ?, ?)",
            (uid, kind, json.dumps(params, ensure_ascii=False), link),
        )


def notification_text(row):
    params = json.loads(row["params"] or "{}")
    if "hood" in params:
        params["hood"] = _(params["hood"])
    return _(TEXTS.get(row["kind"], row["kind"])).format(**params)


def for_current_user(limit=8):
    """Unread count and latest notifications for the bell in the header."""
    if not g.get("user"):
        return 0, []
    db = get_db()
    unread = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL", (g.user["id"],)
    ).fetchone()[0]
    rows = db.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (g.user["id"], limit),
    ).fetchall()
    return unread, rows


@bp.route("/")
@login_required
def all_notifications():
    _unread, rows = for_current_user(limit=50)
    page = render_template("notifications.html", rows=rows)
    mark_all_read()
    return page


def mark_all_read():
    db = get_db()
    db.execute(
        "UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND read_at IS NULL",
        (g.user["id"],),
    )
    db.commit()


@bp.route("/read", methods=("POST",))
@login_required
def read():
    """Called when the bell menu is opened (JavaScript) or submitted as a form."""
    mark_all_read()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True)
    return redirect(request.referrer or url_for("index"))
