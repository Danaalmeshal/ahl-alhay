"""Ahl Al-Hay (أهل الحي) - neighborhood community web application. Sprint 1 + Sprint 2."""
import os
from datetime import timedelta

from flask import Flask, g, redirect, render_template, url_for

from security import login_required

import account
import auth
import community
import db
import help_requests
import i18n
import membership
import moderation
import notices
import notifications
import posts
from i18n import _, current_lang
from security import check_csrf, csrf_token, load_current_user


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-this-key"),
        DATABASE=os.path.join(app.instance_path, "ahl_al_hay.sqlite"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),  # PBI 5B: inactive sessions expire
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(membership.bp)
    app.register_blueprint(help_requests.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(community.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(notices.bp)
    app.register_blueprint(posts.bp)
    app.register_blueprint(moderation.bp)
    app.register_blueprint(i18n.bp)

    @app.before_request
    def before():
        load_current_user()
        check_csrf()

    app.jinja_env.globals.update(csrf_token=csrf_token, _=_, notification_text=notifications.notification_text)

    @app.context_processor
    def layout_data():
        lang = current_lang()
        unread, latest = notifications.for_current_user()
        return {"lang": lang, "dir": "rtl" if lang == "ar" else "ltr", "unread_count": unread, "latest_notifications": latest}

    @app.route("/")
    def index():
        if g.user:
            if g.user["role"] == "admin":
                return redirect(url_for("membership.admin_requests"))
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Resident home: greeting, neighborhood numbers and the latest requests."""
        d = db.get_db()
        hood, me = g.user["neighborhood_id"], g.user["id"]
        stats = {
            "open": d.execute("SELECT COUNT(*) FROM help_requests WHERE neighborhood_id = ? AND status = 'open' AND hidden = 0", (hood,)).fetchone()[0],
            "mine": d.execute("SELECT COUNT(*) FROM help_requests WHERE author_id = ? AND status = 'open' AND hidden = 0", (me,)).fetchone()[0],
            "replies": d.execute("SELECT COUNT(*) FROM replies WHERE author_id = ? AND hidden = 0", (me,)).fetchone()[0],
            "neighbors": d.execute("SELECT COUNT(*) FROM users WHERE neighborhood_id = ?", (hood,)).fetchone()[0],
        }
        base = ("SELECT hr.id, hr.title, hr.category, hr.created_at, u.name AS author_name, "
                "(SELECT COUNT(*) FROM replies r WHERE r.help_request_id = hr.id AND r.hidden = 0) AS reply_count "
                "FROM help_requests hr JOIN users u ON u.id = hr.author_id ")
        latest = d.execute(base + "WHERE hr.neighborhood_id = ? AND hr.status = 'open' AND hr.hidden = 0 AND hr.author_id != ? "
                           "ORDER BY hr.created_at DESC, hr.id DESC LIMIT 5", (hood, me)).fetchall()
        mine = d.execute(base + "WHERE hr.author_id = ? AND hr.status = 'open' AND hr.hidden = 0 ORDER BY hr.created_at DESC, hr.id DESC", (me,)).fetchall()
        return render_template("dashboard.html", stats=stats, latest=latest, mine=mine)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", title=_("غير مسموح"), message=_("ليس لديك صلاحية للوصول إلى هذه الصفحة.")), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", title=_("غير موجود"), message=_("الصفحة أو الطلب غير موجود.")), 404

    @app.errorhandler(400)
    def bad_request(_e):
        return render_template("error.html", title=_("طلب غير صالح"), message=_("انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى.")), 400

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
