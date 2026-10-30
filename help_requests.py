"""Help requests: publish (PBI 7), browse (PBI 8), reply (PBI 9) and resolve (PBI 10).
Every query is limited to the user's neighborhood (PBI 6A)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from i18n import _
from notifications import notify
from security import login_required

bp = Blueprint("help", __name__, url_prefix="/help")

CATEGORIES = ["استعارة غرض", "مساعدة يدوية", "سؤال أو استفسار", "طلب توصية", "أخرى"]


def _get_request_in_my_neighborhood(request_id):
    """PBI 6A: a request from another neighborhood is treated as not found."""
    row = get_db().execute(
        "SELECT hr.*, u.name AS author_name FROM help_requests hr JOIN users u ON u.id = hr.author_id "
        "WHERE hr.id = ? AND hr.neighborhood_id = ?",
        (request_id, g.user["neighborhood_id"]),
    ).fetchone()
    if row is None:
        abort(404)
    return row


# ---------- PBI 8: Browse help requests ----------

@bp.route("/")
@login_required
def list_requests():
    rows = get_db().execute(
        "SELECT hr.id, hr.title, hr.category, hr.created_at, u.name AS author_name, "
        "(SELECT COUNT(*) FROM replies r WHERE r.help_request_id = hr.id) AS reply_count "
        "FROM help_requests hr JOIN users u ON u.id = hr.author_id "
        "WHERE hr.neighborhood_id = ? AND hr.status = 'open' ORDER BY hr.created_at DESC, hr.id DESC",
        (g.user["neighborhood_id"],),
    ).fetchall()
    return render_template("help/list.html", requests=rows)


# ---------- PBI 7: Publish a help request ----------

@bp.route("/new", methods=("GET", "POST"))
@login_required
def new_request():
    form = {"title": "", "category": "", "description": ""}
    errors = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        if not form["title"]:
            errors["title"] = _("العنوان مطلوب.")
        if form["category"] not in CATEGORIES:
            errors["category"] = _("اختر التصنيف من القائمة.")
        if not form["description"]:
            errors["description"] = _("الوصف مطلوب.")
        if not errors:
            db = get_db()
            cur = db.execute(
                "INSERT INTO help_requests (title, category, description, author_id, neighborhood_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (form["title"], form["category"], form["description"], g.user["id"], g.user["neighborhood_id"]),
            )
            neighbors = [r["id"] for r in db.execute(
                "SELECT id FROM users WHERE neighborhood_id = ? AND id != ?", (g.user["neighborhood_id"], g.user["id"]))]
            notify(neighbors, "new_help_request", link=url_for("help.detail", request_id=cur.lastrowid),
                   name=g.user["name"], title=form["title"])
            db.commit()
            flash(_("تم نشر طلبك."), "success")
            return redirect(url_for("help.detail", request_id=cur.lastrowid))
    return render_template("help/new.html", form=form, errors=errors, categories=CATEGORIES)


# ---------- PBI 8 + 9: Request details and replies ----------

@bp.route("/<int:request_id>", methods=("GET", "POST"))
@login_required
def detail(request_id):
    help_request = _get_request_in_my_neighborhood(request_id)
    db = get_db()
    error = None
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if help_request["status"] != "open":
            error = _("لا يمكن الرد على طلب منتهٍ.")
        elif not body:
            error = _("لا يمكن إرسال رد فارغ.")
        else:
            db.execute(
                "INSERT INTO replies (help_request_id, author_id, body) VALUES (?, ?, ?)",
                (request_id, g.user["id"], body),
            )
            link = url_for("help.detail", request_id=request_id) + "#replies"
            if g.user["id"] != help_request["author_id"]:
                notify(help_request["author_id"], "new_reply", link=link, name=g.user["name"], title=help_request["title"])
            else:
                repliers = [r["author_id"] for r in db.execute(
                    "SELECT DISTINCT author_id FROM replies WHERE help_request_id = ? AND author_id != ?", (request_id, g.user["id"]))]
                notify(repliers, "owner_reply", link=link, name=g.user["name"], title=help_request["title"])
            db.commit()
            return redirect(url_for("help.detail", request_id=request_id) + "#replies")
    replies = db.execute(
        "SELECT r.body, r.created_at, r.author_id, u.name AS author_name FROM replies r "
        "JOIN users u ON u.id = r.author_id WHERE r.help_request_id = ? ORDER BY r.created_at, r.id",
        (request_id,),
    ).fetchall()
    return render_template("help/detail.html", req=help_request, replies=replies, error=error)


# ---------- PBI 10: Resolve my help request ----------

@bp.route("/<int:request_id>/resolve", methods=("POST",))
@login_required
def resolve(request_id):
    help_request = _get_request_in_my_neighborhood(request_id)
    if help_request["author_id"] != g.user["id"]:
        abort(403)  # only the owner can resolve, checked on the server
    db = get_db()
    db.execute(
        "UPDATE help_requests SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (request_id,),
    )
    repliers = [r["author_id"] for r in db.execute(
        "SELECT DISTINCT author_id FROM replies WHERE help_request_id = ? AND author_id != ?", (request_id, g.user["id"]))]
    notify(repliers, "request_resolved", link=url_for("help.detail", request_id=request_id), title=help_request["title"])
    db.commit()
    flash(_("تم إغلاق طلبك كـ \"تم الحل\". شكراً لجيرانك!"), "success")
    return redirect(url_for("help.list_requests"))
