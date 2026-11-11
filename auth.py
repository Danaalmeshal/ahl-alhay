"""Accounts: register with an invitation code (PBI 4A), log in and log out (PBI 5A)."""
from flask import Blueprint, flash, g, make_response, redirect, render_template, request, session, url_for
from sqlite3 import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from i18n import _
from notifications import notify
from security import normalize_phone, password_problems, safe_next, session_lang_separator

bp = Blueprint("auth", __name__)


# ---------- PBI 4A: Register using an invitation code ----------

@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    form = {"code": request.args.get("code", ""), "phone": ""}
    errors = {}

    if request.method == "POST":
        form = {
            "code": request.form.get("code", "").strip().upper(),
            "phone": normalize_phone(request.form.get("phone")),
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        db = get_db()

        invite = None
        if not form["code"]:
            errors["code"] = _("كود الدعوة مطلوب.")
        else:
            invite = db.execute(
                "SELECT ic.*, jr.phone AS request_phone, jr.name AS request_name "
                "FROM invitation_codes ic JOIN join_requests jr ON jr.id = ic.join_request_id "
                "WHERE ic.code = ?",
                (form["code"],),
            ).fetchone()
            if invite is None:
                errors["code"] = _("كود الدعوة غير صحيح.")
            elif invite["used_at"] is not None:
                errors["code"] = _("كود الدعوة مستخدم من قبل.")

        if not form["phone"]:
            errors["phone"] = _("رقم الجوال مطلوب.")
        elif invite is not None and "code" not in errors and form["phone"] != invite["request_phone"]:
            errors["phone"] = _("رقم الجوال يجب أن يطابق الرقم المكتوب في طلب الانضمام.")
        elif db.execute("SELECT 1 FROM users WHERE phone = ?", (form["phone"],)).fetchone():
            errors["phone"] = _("رقم الجوال مسجل مسبقاً.")

        problems = password_problems(password)
        if problems:
            errors["password"] = _("كلمة المرور يجب أن تحتوي على: {items}.", items=session_lang_separator().join(problems))
        elif password != confirm:
            errors["confirm_password"] = _("كلمتا المرور غير متطابقتين.")

        if not errors:
            # PBI 4B: account + code usage happen in ONE transaction. If anything fails, nothing is saved
            # and the code stays unused, so the person can try again.
            try:
                used = db.execute(
                    "UPDATE invitation_codes SET used_at = CURRENT_TIMESTAMP WHERE id = ? AND used_at IS NULL",
                    (invite["id"],),
                )
                if used.rowcount != 1:  # e.g. a double click: the first request already used the code
                    db.rollback()
                    errors["code"] = _("كود الدعوة مستخدم من قبل.")
                else:
                    cur = db.execute(
                        "INSERT INTO users (name, phone, password_hash, role, neighborhood_id) "
                        "VALUES (?, ?, ?, 'resident', ?)",
                        (invite["request_name"], form["phone"], generate_password_hash(password), invite["neighborhood_id"]),
                    )
                    hood = db.execute("SELECT name FROM neighborhoods WHERE id = ?", (invite["neighborhood_id"],)).fetchone()["name"]
                    notify(cur.lastrowid, "welcome", link=url_for("help.list_requests"), hood=hood)
                    db.commit()
                    flash(_("تم إنشاء حسابك بنجاح. سجّل دخولك الآن."), "success")
                    return redirect(url_for("auth.login"))
            except (IntegrityError, Exception) as exc:  # noqa: BLE001 - any failure must roll back
                db.rollback()
                if isinstance(exc, IntegrityError):
                    errors["phone"] = _("رقم الجوال مسجل مسبقاً.")
                else:
                    errors["form"] = _("تعذّر إنشاء الحساب. لم يتم استخدام الكود، حاول مرة أخرى.")
    return render_template("auth/register.html", form=form, errors=errors)


# ---------- PBI 5A: Log in and log out ----------

@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    phone = ""
    error = None
    if request.method == "POST":
        phone = normalize_phone(request.form.get("phone"))
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            # One general message: does not reveal whether the phone number exists.
            error = _("رقم الجوال أو كلمة المرور غير صحيحة.")
        else:
            lang = session.get("lang")
            session.clear()
            session["user_id"] = user["id"]
            if lang:
                session["lang"] = lang
            session.permanent = True  # expires after PERMANENT_SESSION_LIFETIME of inactivity
            target = safe_next(request.args.get("next")) or url_for(
                "membership.admin_requests" if user["role"] == "admin" else "dashboard")
            resp = make_response(redirect(target))
            resp.set_cookie("ahl_signed_in", "1", max_age=7 * 24 * 3600, httponly=True, samesite="Lax")
            return resp
    return render_template("auth/login.html", phone=phone, error=error)


@bp.route("/logout", methods=("POST",))
def logout():
    if g.user:
        # Activity status: the user left the site.
        db = get_db()
        db.execute("UPDATE users SET last_seen = NULL WHERE id = ?", (g.user["id"],))
        db.commit()
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    flash(_("تم تسجيل الخروج."), "info")
    resp = make_response(redirect(url_for("auth.login")))
    resp.delete_cookie("ahl_signed_in")
    return resp
