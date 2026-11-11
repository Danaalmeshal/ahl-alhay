"""Reports and moderation: residents report content (PBI 17); the neighborhood administrator reviews them (PBI 18)."""
from sqlite3 import IntegrityError

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from i18n import _
from notifications import notify
from security import admin_required, login_required

bp = Blueprint("moderation", __name__)

# content type -> (table, SQL that finds one item together with its neighborhood, text shown to the administrator)
TYPES = {
    "help": ("help_requests",
             "SELECT x.id, x.neighborhood_id, x.author_id, x.hidden, x.title AS label FROM help_requests x WHERE x.id = ?"),
    "reply": ("replies",
              "SELECT x.id, p.neighborhood_id, x.author_id, x.hidden, x.body AS label FROM replies x "
              "JOIN help_requests p ON p.id = x.help_request_id WHERE x.id = ?"),
    "notice": ("notices",
               "SELECT x.id, x.neighborhood_id, x.author_id, x.hidden, x.description AS label FROM notices x WHERE x.id = ?"),
    "notice_reply": ("notice_replies",
                     "SELECT x.id, p.neighborhood_id, x.author_id, x.hidden, x.body AS label FROM notice_replies x "
                     "JOIN notices p ON p.id = x.notice_id WHERE x.id = ?"),
    "post": ("posts",
             "SELECT x.id, x.neighborhood_id, x.author_id, x.hidden, x.title AS label FROM posts x WHERE x.id = ?"),
    "comment": ("post_comments",
                "SELECT x.id, p.neighborhood_id, x.author_id, x.hidden, x.body AS label FROM post_comments x "
                "JOIN posts p ON p.id = x.post_id WHERE x.id = ?"),
}
TYPE_NAMES = {
    "help": "طلب مساعدة", "reply": "رد على طلب", "notice": "بلاغ حي",
    "notice_reply": "رد على بلاغ", "post": "منشور", "comment": "تعليق",
}


def _find(content_type, content_id):
    """The item must exist, be visible and belong to the current user's neighborhood; otherwise 404 (PBI 6B)."""
    if content_type not in TYPES:
        abort(404)
    row = get_db().execute(TYPES[content_type][1], (content_id,)).fetchone()
    if row is None or row["hidden"] or row["neighborhood_id"] != g.user["neighborhood_id"]:
        abort(404)
    return row


# ---------- PBI 17: Report content ----------

@bp.route("/report/<content_type>/<int:content_id>", methods=("GET", "POST"))
@login_required
def report(content_type, content_id):
    item = _find(content_type, content_id)
    db = get_db()
    error = None
    already = db.execute(
        "SELECT 1 FROM reports WHERE content_type = ? AND content_id = ? AND reporter_id = ?",
        (content_type, content_id, g.user["id"]),
    ).fetchone() is not None
    if already:
        flash(_("سبق أن أبلغت عن هذا المحتوى. العمدة سيراجعه."), "info")
        return redirect(request.referrer or url_for("index"))
    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if not reason:
            error = _("سبب البلاغ مطلوب.")
        else:
            try:
                db.execute(
                    "INSERT INTO reports (content_type, content_id, reporter_id, neighborhood_id, reason) VALUES (?, ?, ?, ?, ?)",
                    (content_type, content_id, g.user["id"], g.user["neighborhood_id"], reason),
                )
            except IntegrityError:  # double submission: the report exists already
                db.rollback()
                flash(_("سبق أن أبلغت عن هذا المحتوى. العمدة سيراجعه."), "info")
                return redirect(url_for("index"))
            admins = [r["id"] for r in db.execute(
                "SELECT id FROM users WHERE role = 'admin' AND neighborhood_id = ?", (g.user["neighborhood_id"],))]
            notify(admins, "new_report", link=url_for("moderation.admin_reports"))
            db.commit()
            flash(_("تم إرسال البلاغ إلى عمدة الحي. شكراً لك."), "success")
            return redirect(url_for("index"))
    return render_template("report.html", item=item, content_type=content_type, type_name=TYPE_NAMES[content_type], error=error)


# ---------- PBI 18: The administrator reviews open reports ----------

@bp.route("/admin/reports")
@admin_required
def admin_reports():
    db = get_db()
    rows = db.execute(
        "SELECT r.*, u.name AS reporter_name FROM reports r JOIN users u ON u.id = r.reporter_id "
        "WHERE r.neighborhood_id = ? AND r.status = 'open' ORDER BY r.created_at, r.id",
        (g.user["neighborhood_id"],),
    ).fetchall()
    items = []
    for r in rows:
        found = db.execute(TYPES[r["content_type"]][1], (r["content_id"],)).fetchone()
        author = db.execute("SELECT name FROM users WHERE id = ?", (found["author_id"],)).fetchone()["name"] if found else ""
        items.append({"report": r, "label": found["label"] if found else "", "author": author,
                      "type_name": TYPE_NAMES[r["content_type"]]})
    return render_template("admin/reports.html", items=items)


def _own_report(report_id):
    row = get_db().execute(
        "SELECT * FROM reports WHERE id = ? AND neighborhood_id = ?", (report_id, g.user["neighborhood_id"])).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/admin/reports/<int:report_id>/<action>", methods=("POST",))
@admin_required
def decide(report_id, action):
    if action not in ("remove", "dismiss"):
        abort(404)
    rep = _own_report(report_id)
    db = get_db()
    if rep["status"] != "open":
        flash(_("تم اتخاذ قرار في هذا البلاغ مسبقاً."), "info")
        return redirect(url_for("moderation.admin_reports"))
    if action == "dismiss":
        db.execute("UPDATE reports SET status = 'dismissed', decided_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'open'",
                   (report_id,))
        db.commit()
        flash(_("تم تجاهل البلاغ. المحتوى باقٍ كما هو."), "success")
        return redirect(url_for("moderation.admin_reports"))
    table, query = TYPES[rep["content_type"]]
    found = db.execute(query, (rep["content_id"],)).fetchone()
    if found is not None:
        db.execute(f"UPDATE {table} SET hidden = 1 WHERE id = ?", (rep["content_id"],))  # table name comes from TYPES, not the user
        if found["author_id"] != g.user["id"]:
            notify(found["author_id"], "content_removed")
    # every open report on the same item is closed together
    db.execute(
        "UPDATE reports SET status = 'removed', decided_at = CURRENT_TIMESTAMP "
        "WHERE content_type = ? AND content_id = ? AND status = 'open' AND neighborhood_id = ?",
        (rep["content_type"], rep["content_id"], g.user["neighborhood_id"]),
    )
    db.commit()
    flash(_("تمت إزالة المحتوى ولن يظهر للسكان."), "success")
    return redirect(url_for("moderation.admin_reports"))
