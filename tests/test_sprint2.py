"""Automated checks for Sprint 2 (run: python -m pytest tests  or  python tests/test_sprint2.py)."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db as dbmod  # noqa: E402
from app import create_app  # noqa: E402


def make_client():
    path = tempfile.mktemp(suffix=".sqlite")
    app = create_app({"DATABASE": path, "TESTING": True})
    with app.app_context():
        dbmod.init_db()
    return app


def main(resp):
    """Only the page content (the bell menu in the header also repeats notification texts)."""
    t = resp.get_data(as_text=True)
    return t[t.index("<main"):t.index("</main>")] if "<main" in t else t


def token(c):
    c.get("/join")
    with c.session_transaction() as s:
        return s.get("_csrf")


def post(c, url, data=None, **kw):
    data = dict(data or {})
    data["_csrf"] = token(c)
    return c.post(url, data=data, **kw)


def login(app, phone, password):
    c = app.test_client()
    r = post(c, "/login", {"phone": phone, "password": password})
    assert r.status_code == 302, r.data
    return c


def make_resident(app, name, phone, hood_id, admin_client):
    jc = app.test_client()
    post(jc, "/join", {"name": name, "phone": phone, "address": "x", "neighborhood_id": hood_id})
    with app.app_context():
        rid = dbmod.get_db().execute("SELECT id FROM join_requests WHERE phone=?", (phone,)).fetchone()["id"]
    post(admin_client, f"/admin/requests/{rid}/approve", {})
    with app.app_context():
        code = dbmod.get_db().execute("SELECT code FROM invitation_codes WHERE join_request_id=?", (rid,)).fetchone()["code"]
    rc = app.test_client()
    r = post(rc, "/register", {"code": code, "phone": phone, "password": "Abcd@123", "confirm_password": "Abcd@123"})
    assert r.status_code == 302
    return login(app, phone, "Abcd@123"), rid, code


def run():
    app = make_client()
    ok = []

    def check(name, cond):
        assert cond, "FAILED: " + name
        ok.append(name)

    omda1 = login(app, "0500000001", "Omda@123")   # الملقا (id 1)
    omda2 = login(app, "0500000002", "Omda@123")   # الياسمين (id 2)
    a, rid_a, code_a = make_resident(app, "سارة", "0511111111", 1, omda1)
    b, _, _ = make_resident(app, "نورة", "0522222222", 1, omda1)
    z, _, _ = make_resident(app, "ليلى", "0533333333", 2, omda2)

    # ---- PBI 2B / 3B ----
    r = post(omda1, f"/admin/requests/{rid_a}/approve", {})
    check("3B repeat approval shows the existing code", r.status_code == 302)
    with app.app_context():
        n = dbmod.get_db().execute("SELECT COUNT(*) FROM invitation_codes WHERE join_request_id=?", (rid_a,)).fetchone()[0]
    check("3B still one code per request", n == 1)
    r = post(omda1, f"/admin/requests/{rid_a}/reject", {"rejection_reason": "x"}, follow_redirects=True)
    check("2B decided request cannot be rejected", "مسبقاً" in r.get_data(as_text=True))
    with app.app_context():
        st = dbmod.get_db().execute("SELECT status FROM join_requests WHERE id=?", (rid_a,)).fetchone()["status"]
    check("2B status unchanged", st == "approved")
    r = post(omda2, f"/admin/requests/{rid_a}/approve", {})
    check("6B other neighborhood's request -> 404", r.status_code == 404)

    # ---- PBI 4B: failed/duplicate registration ----
    r = post(app.test_client(), "/register", {"code": code_a, "phone": "0511111111", "password": "Abcd@123", "confirm_password": "Abcd@123"})
    check("4B used code rejected, no second account", r.status_code == 200)
    with app.app_context():
        n = dbmod.get_db().execute("SELECT COUNT(*) FROM users WHERE phone='0511111111'").fetchone()[0]
    check("4B only one account", n == 1)
    jc = app.test_client()
    post(jc, "/join", {"name": "هند", "phone": "0544444444", "address": "x", "neighborhood_id": 1})
    with app.app_context():
        rid = dbmod.get_db().execute("SELECT id FROM join_requests WHERE phone='0544444444'").fetchone()["id"]
    post(omda1, f"/admin/requests/{rid}/approve", {})
    with app.app_context():
        code = dbmod.get_db().execute("SELECT code FROM invitation_codes WHERE join_request_id=?", (rid,)).fetchone()["code"]
    bad = post(app.test_client(), "/register", {"code": code, "phone": "0544444444", "password": "abc", "confirm_password": "abc"})
    with app.app_context():
        used = dbmod.get_db().execute("SELECT used_at FROM invitation_codes WHERE code=?", (code,)).fetchone()["used_at"]
    check("4B invalid password: code stays unused", bad.status_code == 200 and used is None)
    good = post(app.test_client(), "/register", {"code": code, "phone": "0544444444", "password": "Abcd@123", "confirm_password": "Abcd@123"})
    check("4B retry succeeds", good.status_code == 302)

    # ---- PBI 5B: session expiry ----
    c = login(app, "0511111111", "Abcd@123")
    c.set_cookie("ahl_signed_in", "1")
    with c.session_transaction() as s:
        s.clear()  # simulates an expired session
    r = c.get("/notices/?category=%D8%AA%D8%B3%D8%B1%D8%A8+%D9%85%D9%8A%D8%A7%D9%87")
    check("5B redirected to login with next", r.status_code == 302 and "next=" in r.headers["Location"])
    r = c.get(r.headers["Location"])
    check("5B expired-session message", "انتهت الجلسة" in r.get_data(as_text=True))
    t = token(c)
    r = c.post(r.request.full_path.rstrip("?"), data={"phone": "0511111111", "password": "Abcd@123", "_csrf": t})
    check("5B returns to the requested page after login", r.status_code == 302 and r.headers["Location"].startswith("/notices/"))
    r = c.post("/login?next=//evil.com", data={"phone": "0511111111", "password": "Abcd@123", "_csrf": token(c)})
    # already logged in => redirect to dashboard; test open-redirect with a fresh client
    c2 = app.test_client()
    r = post(c2, "/login?next=//evil.com", {"phone": "0511111111", "password": "Abcd@123"})
    check("5B open redirect refused", "evil.com" not in r.headers["Location"])
    check("5B anonymous visit redirects to login", app.test_client().get("/posts/").status_code == 302)

    # ---- PBI 11-14 notices ----
    r = post(a, "/notices/new", {"category": "تسرب مياه", "description": "", "location": ""})
    check("11 required fields", r.status_code == 200 and "مطلوب" in r.get_data(as_text=True))
    r = post(a, "/notices/new", {"category": "تسرب مياه", "description": "ماء في الشارع", "location": "شارع 15"})
    check("11 publish", r.status_code == 302)
    nid = int(re.search(r"/notices/(\d+)", r.headers["Location"]).group(1))
    post(a, "/notices/new", {"category": "حيوان أليف مفقود", "description": "قطة", "location": "الحديقة"})
    page = main(b.get("/notices/"))
    check("12 same-neighborhood resident sees notices", "شارع 15" in page and "الحديقة" in page)
    check("12 newest first", page.index("الحديقة") < page.index("شارع 15"))
    check("12 other neighborhood sees none", "شارع 15" not in main(z.get("/notices/")))
    check("6B other neighborhood detail -> 404", z.get(f"/notices/{nid}").status_code == 404)
    check("12 category filter", "الحديقة" not in main(b.get("/notices/?category=تسرب مياه")))
    check("12 empty message", "لا توجد بلاغات مطابقة" in main(b.get("/notices/?category=أخرى")))
    r = post(b, f"/notices/{nid}", {"body": "  "})
    check("13 empty reply rejected", "رد فارغ" in r.get_data(as_text=True))
    r = post(b, f"/notices/{nid}", {"body": "أنا شفته"})
    check("13 reply saved", r.status_code == 302 and "أنا شفته" in main(a.get(f"/notices/{nid}")))
    check("6B other neighborhood cannot reply", post(z, f"/notices/{nid}", {"body": "hi"}).status_code == 404)
    check("14 non-owner cannot resolve (403)", post(b, f"/notices/{nid}/resolve").status_code == 403)
    check("14 owner resolves", post(a, f"/notices/{nid}/resolve").status_code == 302)
    check("14 resolved filter", "شارع 15" in main(b.get("/notices/?status=resolved"))
          and "شارع 15" not in main(b.get("/notices/?status=open")))
    check("12 combined filters", "شارع 15" in main(b.get("/notices/?category=تسرب مياه&status=resolved")))

    # ---- PBI 15-16 posts ----
    r = post(a, "/posts/new", {"title": "", "body": ""})
    check("15 required", r.status_code == 200 and "مطلوب" in r.get_data(as_text=True))
    r = post(a, "/posts/new", {"title": "توزيع قهوة", "body": "بعد صلاة الجمعة"})
    pid = int(re.search(r"/posts/(\d+)", r.headers["Location"]).group(1))
    check("15 publish", r.status_code == 302)
    check("16 visible to neighbors", "توزيع قهوة" in main(b.get("/posts/")))
    check("16 hidden from other neighborhood", "توزيع قهوة" not in main(z.get("/posts/"))
          and z.get(f"/posts/{pid}").status_code == 404)
    check("16 empty comment rejected", "تعليق فارغ" in post(b, f"/posts/{pid}", {"body": " "}).get_data(as_text=True))
    post(b, f"/posts/{pid}", {"body": "شكراً"})
    post(a, f"/posts/{pid}", {"body": "العفو"})
    page = main(a.get(f"/posts/{pid}"))
    check("16 comments newest first", page.index("العفو") < page.index("شكراً"))
    check("6B other neighborhood cannot comment", post(z, f"/posts/{pid}", {"body": "x"}).status_code == 404)

    # ---- PBI 17-18 reports ----
    with app.app_context():
        cid = dbmod.get_db().execute("SELECT id FROM post_comments WHERE body='شكراً'").fetchone()["id"]
    check("17 report form opens", a.get(f"/report/comment/{cid}").status_code == 200)
    check("17 reason required", "مطلوب" in post(a, f"/report/comment/{cid}", {"reason": ""}).get_data(as_text=True))
    check("6B cannot report other neighborhood's item", post(z, f"/report/comment/{cid}", {"reason": "x"}).status_code == 404)
    check("17 report saved", post(a, f"/report/comment/{cid}", {"reason": "إساءة"}).status_code == 302)
    r = a.get(f"/report/comment/{cid}", follow_redirects=True)
    check("17 same item twice refused", "سبق أن أبلغت" in r.get_data(as_text=True))
    post(a, f"/report/comment/{cid}", {"reason": "مرة ثانية"})
    with app.app_context():
        n = dbmod.get_db().execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    check("17 one report per person per item", n == 1)
    check("18 residents cannot open the queue", a.get("/admin/reports").status_code == 403)
    check("18 other Omda sees nothing", "إساءة" not in main(omda2.get("/admin/reports")))
    check("18 Omda sees the report", "إساءة" in omda1.get("/admin/reports").get_data(as_text=True))
    with app.app_context():
        repid = dbmod.get_db().execute("SELECT id FROM reports").fetchone()["id"]
    check("18 other Omda cannot decide (404)", post(omda2, f"/admin/reports/{repid}/remove").status_code == 404)
    check("18 resident cannot decide (403)", post(a, f"/admin/reports/{repid}/remove").status_code == 403)
    check("18 remove", post(omda1, f"/admin/reports/{repid}/remove").status_code == 302)
    check("18 removed content hidden", "شكراً" not in main(a.get(f"/posts/{pid}")))
    check("18 decided once", "مسبقاً" in post(omda1, f"/admin/reports/{repid}/dismiss", follow_redirects=True).get_data(as_text=True))
    # dismiss path + removal of a whole post
    post(b, f"/report/post/{pid}", {"reason": "غير مناسب"})
    with app.app_context():
        r2 = dbmod.get_db().execute("SELECT id FROM reports WHERE status='open'").fetchone()["id"]
    post(omda1, f"/admin/reports/{r2}/dismiss")
    check("18 dismiss keeps content", "توزيع قهوة" in main(b.get("/posts/")))
    # help requests/replies can be reported and removed too
    r = post(a, "/help/new", {"title": "سلم", "category": "استعارة غرض", "description": "أحتاج سلم"})
    hid = int(re.search(r"/help/(\d+)", r.headers["Location"]).group(1))
    post(b, f"/help/{hid}", {"body": "رد مسيء"})
    with app.app_context():
        rep_id = dbmod.get_db().execute("SELECT id FROM replies").fetchone()["id"]
    post(a, f"/report/reply/{rep_id}", {"reason": "مسيء"})
    with app.app_context():
        r3 = dbmod.get_db().execute("SELECT id FROM reports WHERE status='open'").fetchone()["id"]
    post(omda1, f"/admin/reports/{r3}/remove")
    check("18 removed reply hidden", "رد مسيء" not in main(a.get(f"/help/{hid}")))
    check("removed author is notified", "إزالة محتواك" in b.get("/notifications/").get_data(as_text=True))

    # ---- English interface renders ----
    en = app.test_client()
    en.get("/lang/en")
    r = post(en, "/login", {"phone": "0511111111", "password": "Abcd@123"})
    for url in ("/notices/", "/notices/new", "/posts/", "/posts/new"):
        txt = en.get(url).get_data(as_text=True)
        body = re.sub(r"<(script|style).*?</\1>", "", txt, flags=re.S)
        body = re.sub(r"<[^>]+>", " ", body)
        arabic = set(re.findall(r"[؀-ۿ]+", body))
        print(url, "Arabic words left in EN page:", sorted(arabic)[:8])
    print(f"{len(ok)} checks passed")


if __name__ == "__main__":
    run()


def test_sprint2():
    run()
