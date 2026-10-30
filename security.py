"""Shared helpers: current user, access decorators, CSRF protection, validation rules."""
import functools
import re
import secrets

from flask import abort, flash, g, redirect, request, session, url_for

from db import get_db
from i18n import _

ACTIVE_WINDOW_SECONDS = 120  # "active" = seen on the site within the last 2 minutes

# ---------- Current user and access control (PBI 5A / 6A) ----------

def load_current_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT u.*, n.name AS neighborhood_name FROM users u "
            "JOIN neighborhoods n ON n.id = u.neighborhood_id WHERE u.id = ?",
            (user_id,),
        ).fetchone()
        if g.user is None:
            session.pop("user_id", None)
        else:
            # Activity status: remember that this user is on the site right now.
            db = get_db()
            db.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
            db.commit()


def login_required(view):
    """Protected pages redirect to the login page when there is no session."""
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            flash(_("الرجاء تسجيل الدخول أولاً."), "info")
            return redirect(url_for("auth.login"))
        return view(**kwargs)
    return wrapped


def admin_required(view):
    """Administrator pages are available only to administrators (checked on the server)."""
    @functools.wraps(view)
    @login_required
    def wrapped(**kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return view(**kwargs)
    return wrapped


# ---------- CSRF protection for every POST form ----------

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400)


# ---------- Validation rules ----------

PHONE_RE = re.compile(r"^05\d{8}$")  # Saudi mobile: 05XXXXXXXX


def normalize_phone(phone):
    """Remove spaces and convert Arabic-Indic digits so ٠٥٠ and 050 are the same number."""
    phone = (phone or "").strip().replace(" ", "")
    return phone.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))


def valid_phone(phone):
    return bool(PHONE_RE.match(phone))


def password_problems(password):
    """PBI 4A rule: at least 4 letters, 1 symbol and 3 numbers. Returns a list of missing parts."""
    letters = sum(ch.isalpha() for ch in password)
    digits = sum(ch.isdigit() for ch in password)
    symbols = sum((not ch.isalnum()) and (not ch.isspace()) for ch in password)
    problems = []
    if letters < 4:
        problems.append(_("4 أحرف على الأقل"))
    if symbols < 1:
        problems.append(_("رمز واحد على الأقل مثل @ أو #"))
    if digits < 3:
        problems.append(_("3 أرقام على الأقل"))
    return problems


# ---------- Invitation codes (PBI 3A) ----------

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to avoid confusion


def new_invitation_code(db):
    """Random 8-character code that does not exist yet."""
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if db.execute("SELECT 1 FROM invitation_codes WHERE code = ?", (code,)).fetchone() is None:
            return code


def session_lang_separator():
    """List separator for error messages: Arabic comma or English comma."""
    return ", " if session.get("lang") == "en" else "، "
