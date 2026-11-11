"""Community posts: publish (PBI 15), read and comment (PBI 16). Limited to the user's neighborhood (PBI 6B)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from i18n import _
from notifications import notify
from security import login_required

bp = Blueprint("posts", __name__, url_prefix="/posts")


def _get_post(post_id):
    row = get_db().execute(
        "SELECT p.*, u.name AS author_name FROM posts p JOIN users u ON u.id = p.author_id "
        "WHERE p.id = ? AND p.neighborhood_id = ? AND p.hidden = 0",
        (post_id, g.user["neighborhood_id"]),
    ).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/")
@login_required
def list_posts():
    rows = get_db().execute(
        "SELECT p.id, p.title, p.body, p.created_at, u.name AS author_name, "
        "(SELECT COUNT(*) FROM post_comments c WHERE c.post_id = p.id AND c.hidden = 0) AS comment_count "
        "FROM posts p JOIN users u ON u.id = p.author_id WHERE p.neighborhood_id = ? AND p.hidden = 0 "
        "ORDER BY p.created_at DESC, p.id DESC",
        (g.user["neighborhood_id"],),
    ).fetchall()
    return render_template("posts/list.html", posts=rows)


@bp.route("/new", methods=("GET", "POST"))
@login_required
def new_post():
    form = {"title": "", "body": ""}
    errors = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        if not form["title"]:
            errors["title"] = _("العنوان مطلوب.")
        if not form["body"]:
            errors["body"] = _("نص المنشور مطلوب.")
        if not errors:
            db = get_db()
            cur = db.execute(
                "INSERT INTO posts (title, body, author_id, neighborhood_id) VALUES (?, ?, ?, ?)",
                (form["title"], form["body"], g.user["id"], g.user["neighborhood_id"]),
            )
            db.commit()
            flash(_("تم نشر المنشور."), "success")
            return redirect(url_for("posts.detail", post_id=cur.lastrowid))
    return render_template("posts/new.html", form=form, errors=errors)


@bp.route("/<int:post_id>", methods=("GET", "POST"))
@login_required
def detail(post_id):
    post = _get_post(post_id)
    db = get_db()
    error = None
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            error = _("لا يمكن إرسال تعليق فارغ.")
        else:
            db.execute("INSERT INTO post_comments (post_id, author_id, body) VALUES (?, ?, ?)", (post_id, g.user["id"], body))
            if g.user["id"] != post["author_id"]:
                notify(post["author_id"], "post_comment", link=url_for("posts.detail", post_id=post_id) + "#comments",
                       name=g.user["name"], title=post["title"])
            db.commit()
            return redirect(url_for("posts.detail", post_id=post_id) + "#comments")
    comments = db.execute(
        "SELECT c.id, c.body, c.created_at, c.author_id, u.name AS author_name FROM post_comments c "
        "JOIN users u ON u.id = c.author_id WHERE c.post_id = ? AND c.hidden = 0 ORDER BY c.created_at DESC, c.id DESC",
        (post_id,),
    ).fetchall()
    return render_template("posts/detail.html", post=post, comments=comments, error=error)
