"""Neighborhood notices: publish (PBI 11), browse and filter (PBI 12), reply (PBI 13), resolve (PBI 14).
Every query is limited to the user's neighborhood (PBI 6B)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from i18n import _
from notifications import notify
from security import login_required

bp = Blueprint("notices", __name__, url_prefix="/notices")

CATEGORIES = ["حيوان أليف مفقود", "تسرب مياه", "تلف جدار أو طريق", "أخرى"]


def _get_notice(notice_id):
    """A notice from another neighborhood (or a removed one) is treated as not found."""
    row = get_db().execute(
        "SELECT n.*, u.name AS author_name FROM notices n JOIN users u ON u.id = n.author_id "
        "WHERE n.id = ? AND n.neighborhood_id = ? AND n.hidden = 0",
        (notice_id, g.user["neighborhood_id"]),
    ).fetchone()
    if row is None:
        abort(404)
    return row


# ---------- PBI 12: Browse and filter ----------

@bp.route("/")
@login_required
def list_notices():
    category = request.args.get("category", "")
    status = request.args.get("status", "")
    sql = ("SELECT n.id, n.category, n.description, n.location, n.status, n.created_at, u.name AS author_name, "
           "(SELECT COUNT(*) FROM notice_replies r WHERE r.notice_id = n.id AND r.hidden = 0) AS reply_count "
           "FROM notices n JOIN users u ON u.id = n.author_id WHERE n.neighborhood_id = ? AND n.hidden = 0")
    args = [g.user["neighborhood_id"]]
    if category in CATEGORIES:  # both filters can be combined
        sql += " AND n.category = ?"
        args.append(category)
    else:
        category = ""
    if status in ("open", "resolved"):
        sql += " AND n.status = ?"
        args.append(status)
    else:
        status = ""
    rows = get_db().execute(sql + " ORDER BY n.created_at DESC, n.id DESC", args).fetchall()
    return render_template("notices/list.html", notices=rows, categories=CATEGORIES, category=category, status=status)


# ---------- PBI 11: Publish ----------

@bp.route("/new", methods=("GET", "POST"))
@login_required
def new_notice():
    form = {"category": "", "description": "", "location": ""}
    errors = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        if form["category"] not in CATEGORIES:
            errors["category"] = _("اختر التصنيف من القائمة.")
        if not form["description"]:
            errors["description"] = _("الوصف مطلوب.")
        if not form["location"]:
            errors["location"] = _("وصف الموقع مطلوب.")
        if not errors:
            db = get_db()
            cur = db.execute(
                "INSERT INTO notices (category, description, location, author_id, neighborhood_id) VALUES (?, ?, ?, ?, ?)",
                (form["category"], form["description"], form["location"], g.user["id"], g.user["neighborhood_id"]),
            )
            neighbors = [r["id"] for r in db.execute(
                "SELECT id FROM users WHERE neighborhood_id = ? AND id != ?", (g.user["neighborhood_id"], g.user["id"]))]
            notify(neighbors, "new_notice", link=url_for("notices.detail", notice_id=cur.lastrowid),
                   name=g.user["name"], category=form["category"], location=form["location"])
            db.commit()
            flash(_("تم نشر البلاغ."), "success")
            return redirect(url_for("notices.detail", notice_id=cur.lastrowid))
    return render_template("notices/new.html", form=form, errors=errors, categories=CATEGORIES)


# ---------- PBI 13: Details and replies ----------

@bp.route("/<int:notice_id>", methods=("GET", "POST"))
@login_required
def detail(notice_id):
    notice = _get_notice(notice_id)
    db = get_db()
    error = None
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            error = _("لا يمكن إرسال رد فارغ.")
        else:
            db.execute("INSERT INTO notice_replies (notice_id, author_id, body) VALUES (?, ?, ?)",
                       (notice_id, g.user["id"], body))
            if g.user["id"] != notice["author_id"]:
                notify(notice["author_id"], "notice_reply", link=url_for("notices.detail", notice_id=notice_id) + "#replies",
                       name=g.user["name"], category=notice["category"])
            db.commit()
            return redirect(url_for("notices.detail", notice_id=notice_id) + "#replies")
    replies = db.execute(
        "SELECT r.id, r.body, r.created_at, r.author_id, u.name AS author_name FROM notice_replies r "
        "JOIN users u ON u.id = r.author_id WHERE r.notice_id = ? AND r.hidden = 0 ORDER BY r.created_at, r.id",
        (notice_id,),
    ).fetchall()
    return render_template("notices/detail.html", notice=notice, replies=replies, error=error)


# ---------- PBI 14: Mark as resolved (owner only) ----------

@bp.route("/<int:notice_id>/resolve", methods=("POST",))
@login_required
def resolve(notice_id):
    notice = _get_notice(notice_id)
    if notice["author_id"] != g.user["id"]:
        abort(403)  # checked on the server, not only by hiding the button
    db = get_db()
    db.execute("UPDATE notices SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'open'",
               (notice_id,))
    repliers = [r["author_id"] for r in db.execute(
        "SELECT DISTINCT author_id FROM notice_replies WHERE notice_id = ? AND author_id != ?", (notice_id, g.user["id"]))]
    notify(repliers, "notice_resolved", link=url_for("notices.detail", notice_id=notice_id), category=notice["category"])
    db.commit()
    flash(_("تم إغلاق البلاغ كـ \"تم الحل\"."), "success")
    return redirect(url_for("notices.detail", notice_id=notice_id))
