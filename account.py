"""Personal account page: view and edit my information, change my password."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from i18n import _
from security import login_required, normalize_phone, password_problems, session_lang_separator, valid_phone

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.route("/", methods=("GET", "POST"))
@login_required
def profile():
    form = {"name": g.user["name"], "phone": g.user["phone"]}
    errors = {}
    if request.method == "POST":
        form = {"name": request.form.get("name", "").strip(), "phone": normalize_phone(request.form.get("phone"))}
        db = get_db()
        if not form["name"]:
            errors["name"] = _("الاسم مطلوب.")
        if not form["phone"]:
            errors["phone"] = _("رقم الجوال مطلوب.")
        elif not valid_phone(form["phone"]):
            errors["phone"] = _("رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام.")
        elif db.execute("SELECT 1 FROM users WHERE phone = ? AND id != ?", (form["phone"], g.user["id"])).fetchone():
            errors["phone"] = _("رقم الجوال مسجل مسبقاً.")
        if not errors:
            db.execute("UPDATE users SET name = ?, phone = ? WHERE id = ?", (form["name"], form["phone"], g.user["id"]))
            db.commit()
            flash(_("تم حفظ معلوماتك."), "success")
            return redirect(url_for("account.profile"))
    return render_template("account.html", form=form, errors=errors, pw_errors={})


@bp.route("/password", methods=("POST",))
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")
    pw_errors = {}
    if not check_password_hash(g.user["password_hash"], current):
        pw_errors["current_password"] = _("كلمة المرور الحالية غير صحيحة.")
    problems = password_problems(new)
    if problems:
        pw_errors["password"] = _("كلمة المرور يجب أن تحتوي على: {items}.", items=session_lang_separator().join(problems))
    elif new != confirm:
        pw_errors["confirm_password"] = _("كلمتا المرور غير متطابقتين.")
    if pw_errors:
        form = {"name": g.user["name"], "phone": g.user["phone"]}
        return render_template("account.html", form=form, errors={}, pw_errors=pw_errors)
    db = get_db()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), g.user["id"]))
    db.commit()
    flash(_("تم تغيير كلمة المرور."), "success")
    return redirect(url_for("account.profile"))
