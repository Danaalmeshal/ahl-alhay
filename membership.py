"""Membership: join request (PBI 1), request status (PBI 25), administrator review (PBI 2A)
and automatic invitation codes (PBI 3A)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from i18n import _
from notifications import notify
from security import admin_required, new_invitation_code, normalize_phone, valid_phone

bp = Blueprint("membership", __name__)


# ---------- PBI 1: Request neighborhood membership ----------

@bp.route("/join", methods=("GET", "POST"))
def join():
    db = get_db()
    neighborhoods = db.execute("SELECT id, name FROM neighborhoods ORDER BY name").fetchall()
    form = {"name": "", "phone": "", "address": "", "neighborhood_id": ""}
    errors = {}

    if request.method == "POST":
        form = {
            "name": request.form.get("name", "").strip(),
            "phone": normalize_phone(request.form.get("phone")),
            "address": request.form.get("address", "").strip(),
            "neighborhood_id": request.form.get("neighborhood_id", ""),
        }
        if not form["name"]:
            errors["name"] = _("الاسم مطلوب.")
        if not form["phone"]:
            errors["phone"] = _("رقم الجوال مطلوب.")
        elif not valid_phone(form["phone"]):
            errors["phone"] = _("رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام.")
        if not form["address"]:
            errors["address"] = _("العنوان مطلوب.")
        valid_ids = {str(n["id"]) for n in neighborhoods}
        if form["neighborhood_id"] not in valid_ids:
            errors["neighborhood_id"] = _("اختر الحي من القائمة.")

        if not errors:
            cur = db.execute(
                "INSERT INTO join_requests (name, phone, address, neighborhood_id) VALUES (?, ?, ?, ?)",
                (form["name"], form["phone"], form["address"], int(form["neighborhood_id"])),
            )
            admins = [r["id"] for r in db.execute(
                "SELECT id FROM users WHERE role = 'admin' AND neighborhood_id = ?", (int(form["neighborhood_id"]),))]
            notify(admins, "new_join_request", link=url_for("membership.admin_requests"), name=form["name"])
            db.commit()
            return render_template("membership/join_done.html", request_number=cur.lastrowid)

    return render_template("membership/join.html", neighborhoods=neighborhoods, form=form, errors=errors)


# ---------- PBI 25: Check join-request status ----------

@bp.route("/status", methods=("GET", "POST"))
def status():
    result = None
    error = None
    request_number = ""
    if request.method == "POST":
        request_number = request.form.get("request_number", "").strip()
        phone = normalize_phone(request.form.get("phone"))
        number = normalize_phone(request_number)  # also converts Arabic-Indic digits
        row = None
        if number.isdigit() and phone:
            row = get_db().execute(
                "SELECT jr.*, n.name AS neighborhood_name, ic.code, ic.used_at "
                "FROM join_requests jr JOIN neighborhoods n ON n.id = jr.neighborhood_id "
                "LEFT JOIN invitation_codes ic ON ic.join_request_id = jr.id "
                "WHERE jr.id = ? AND jr.phone = ?",
                (int(number), phone),
            ).fetchone()
        if row is None:
            # Same message for a wrong number or a wrong phone: reveals no details.
            error = _("لم نجد طلباً بهذه البيانات. تأكد من رقم الطلب ورقم الجوال.")
        else:
            result = row
    return render_template("membership/status.html", result=result, error=error, request_number=request_number)


# ---------- PBI 2A + 3A: Administrator reviews requests; code generated on approval ----------

@bp.route("/admin/requests")
@admin_required
def admin_requests():
    db = get_db()
    pending = db.execute(
        "SELECT * FROM join_requests WHERE neighborhood_id = ? AND status = 'pending' ORDER BY created_at",
        (g.user["neighborhood_id"],),
    ).fetchall()
    decided = db.execute(
        "SELECT jr.*, ic.code, ic.used_at FROM join_requests jr "
        "LEFT JOIN invitation_codes ic ON ic.join_request_id = jr.id "
        "WHERE jr.neighborhood_id = ? AND jr.status != 'pending' ORDER BY jr.decided_at DESC LIMIT 20",
        (g.user["neighborhood_id"],),
    ).fetchall()
    hood = g.user["neighborhood_id"]
    stats = {
        "pending": len(pending),
        "residents": db.execute("SELECT COUNT(*) FROM users WHERE neighborhood_id = ? AND role = 'resident'", (hood,)).fetchone()[0],
        "open_help": db.execute("SELECT COUNT(*) FROM help_requests WHERE neighborhood_id = ? AND status = 'open' AND hidden = 0", (hood,)).fetchone()[0],
    }
    return render_template("admin/requests.html", pending=pending, decided=decided, stats=stats)


def _own_request(request_id):
    """Only requests of the administrator's own neighborhood can be opened (others look like "not found")."""
    row = get_db().execute(
        "SELECT * FROM join_requests WHERE id = ? AND neighborhood_id = ?",
        (request_id, g.user["neighborhood_id"]),
    ).fetchone()
    if row is None:
        abort(404)
    return row


def _already_decided_message(row):
    """PBI 2B: a request that already has a decision cannot be decided again; say so clearly."""
    state = _("مقبول") if row["status"] == "approved" else _("مرفوض")
    flash(_("طلب {name} تم اتخاذ قرار فيه مسبقاً ({state}). حدّث الصفحة لرؤية آخر حالة.", name=row["name"], state=state), "info")


@bp.route("/admin/requests/<int:request_id>/approve", methods=("POST",))
@admin_required
def approve(request_id):
    row = _own_request(request_id)
    db = get_db()
    if row["status"] == "approved":
        # PBI 3B: approving again never creates a second code; the existing one is shown.
        existing = db.execute("SELECT code, used_at FROM invitation_codes WHERE join_request_id = ?", (request_id,)).fetchone()
        if existing is not None and existing["used_at"] is None:
            flash(_("الطلب مقبول مسبقاً. كود الدعوة الحالي: {code}.", code=existing["code"]), "info")
        else:
            _already_decided_message(row)
        return redirect(url_for("membership.admin_requests"))
    if row["status"] != "pending":
        _already_decided_message(row)
        return redirect(url_for("membership.admin_requests"))
    welcome = request.form.get("welcome_message", "").strip() or None
    # The status change and the code are saved together (one active code per request: join_request_id is UNIQUE).
    changed = db.execute(
        "UPDATE join_requests SET status = 'approved', welcome_message = ?, decided_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND status = 'pending'",
        (welcome, request_id),
    )
    if changed.rowcount != 1:  # someone decided it a moment ago
        db.rollback()
        _already_decided_message(_own_request(request_id))
        return redirect(url_for("membership.admin_requests"))
    code = new_invitation_code(db)
    db.execute(
        "INSERT INTO invitation_codes (code, join_request_id, neighborhood_id) VALUES (?, ?, ?)",
        (code, request_id, row["neighborhood_id"]),
    )
    db.commit()
    flash(_("تم قبول طلب {name}. كود الدعوة: {code} (يظهر للمتقدم في صفحة متابعة الطلب).", name=row["name"], code=code), "success")
    return redirect(url_for("membership.admin_requests"))


@bp.route("/admin/requests/<int:request_id>/reject", methods=("POST",))
@admin_required
def reject(request_id):
    row = _own_request(request_id)
    if row["status"] != "pending":
        _already_decided_message(row)
        return redirect(url_for("membership.admin_requests"))
    reason = request.form.get("rejection_reason", "").strip()
    if not reason:
        flash(_("لا يمكن الرفض بدون كتابة السبب."), "error")
        return redirect(url_for("membership.admin_requests"))
    db = get_db()
    db.execute(
        "UPDATE join_requests SET status = 'rejected', rejection_reason = ?, decided_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND status = 'pending'",
        (reason, request_id),
    )
    db.commit()
    flash(_("تم رفض طلب {name}.", name=row["name"]), "success")
    return redirect(url_for("membership.admin_requests"))
