"""Arabic / English interface. Arabic is the default; English text comes from the EN dictionary.
Usage in Python and Jinja: _("نص عربي") or _("مرحباً {name}", name=...)."""
from urllib.parse import urlparse

from flask import Blueprint, redirect, request, session, url_for

bp = Blueprint("i18n", __name__)

LANGS = ("ar", "en")


def current_lang():
    try:
        lang = session.get("lang", "ar")
    except RuntimeError:  # outside a request
        lang = "ar"
    return lang if lang in LANGS else "ar"


def _(text, **kwargs):
    """A key may carry a context after "||" (same Arabic, different English); it is never shown."""
    if current_lang() == "en":
        text = EN.get(text, text)
    text = text.split("||", 1)[0]
    return text.format(**kwargs) if kwargs else text


@bp.route("/lang/<code>")
def set_lang(code):
    if code in LANGS:
        session["lang"] = code
    # Go back to the same page (path only, so it can never redirect to another site).
    ref = urlparse(request.referrer or "")
    target = ref.path or url_for("index")
    if not target.startswith("/") or target.startswith("//"):
        target = url_for("index")
    elif ref.query:
        target += "?" + ref.query
    return redirect(target)


EN = {
    # ---- layout ----
    "أهل الحي": "Ahl Al-Hay",
    "أهل الحي||page": "Neighbors",
    "الجار قبل الدار": "Neighbors come first",
    "الرئيسية": "Home",
    "طلبات المساعدة": "Help requests",
    "طلب جديد": "New request",
    "الحساب الشخصي": "My account",
    "طلبات الانضمام": "Join requests",
    "طلب انضمام": "Join",
    "متابعة طلبي": "Track my request",
    "إنشاء حساب": "Create account",
    "تسجيل الدخول": "Log in",
    "خروج": "Log out",
    "التنبيهات": "Notifications",
    "لا توجد تنبيهات.": "No notifications.",
    "عرض كل التنبيهات": "View all notifications",
    "جديد": "New",
    "تبديل اللغة": "Switch language",
    "تبديل الوضع الليلي والنهاري": "Toggle dark and light mode",
    "العمدة · مشرف الحي": "Omda · Neighborhood admin",
    "العمدة": "Omda",
    "ساكن": "Resident",
    "ساكن · حي {hood}": "Resident · {hood}",
    "حي {hood}": "{hood} neighborhood",
    "مرحباً،": "Welcome,",
    "أهل الحي · الجار قبل الدار": "Ahl Al-Hay · Neighbors come first",
    "القائمة الرئيسية": "Main menu",
    # ---- neighborhoods and categories (stored in Arabic) ----
    "الملقا": "Al-Malqa",
    "الياسمين": "Al-Yasmin",
    "استعارة غرض": "Borrow an item",
    "مساعدة يدوية": "Hands-on help",
    "سؤال أو استفسار": "Question",
    "طلب توصية": "Recommendation",
    "أخرى": "Other",
    # ---- home ----
    "الرئيسية · أهل الحي": "Home · Ahl Al-Hay",
    "مجتمع حيّك في مكان واحد": "Your neighborhood in one place",
    "جيرانك أقرب<br>مما تتوقع": "Your neighbors are<br>closer than you think",
    "اطلب سلّم، اسأل عن سبّاك، أو مدّ يد العون لجارك. كل شيء داخل حيّك فقط، وبعضوية يوافق عليها عمدة الحي.":
        "Borrow a ladder, ask for a good plumber, or lend your neighbor a hand. Everything stays inside your neighborhood, with membership approved by the Omda.",
    "اطلب الانضمام لحيّك": "Join your neighborhood",
    "لدي حساب": "I have an account",
    "كيف تنضم؟": "How to join",
    "اطرق الباب": "Knock on the door",
    "أرسل طلب انضمام باسمك وجوالك وحيّك وعنوانك، وتحصل على رقم طلب.":
        "Send a join request with your name, phone, neighborhood and address, and get a request number.",
    "العمدة يفتح لك": "The Omda lets you in",
    "بعد موافقة عمدة الحي يظهر لك كود الدعوة في صفحة متابعة الطلب.":
        "Once the Omda approves, your invitation code appears on the request-status page.",
    "أهلاً بك يا جار": "Welcome, neighbor",
    "سجّل حسابك بالكود، وابدأ تساعد جيرانك ويساعدونك.": "Create your account with the code and start helping your neighbors.",
    # ---- dashboard ----
    "هذا ما يحدث في حيّك اليوم": "Here is what's happening in your neighborhood today",
    "طلب مفتوح في الحي": "open requests in the neighborhood",
    "طلباتي المفتوحة": "my open requests",
    "ردودي على الجيران": "my replies to neighbors",
    "عضو في الحي": "members in the neighborhood",
    "اطلب مساعدة": "Ask for help",
    "استعارة غرض، سؤال، توصية…": "Borrow an item, ask a question, get a recommendation…",
    "ساعد جارك": "Help a neighbor",
    "تصفح كل الطلبات المفتوحة": "Browse all open requests",
    "جيرانك يحتاجون": "Your neighbors need",
    "عرض الكل": "View all",
    "لا توجد طلبات من جيرانك حالياً.": "There are no requests from your neighbors right now.",
    "طلباتي": "My requests",
    "ليس لديك طلبات مفتوحة.": "You have no open requests.",
    "انشر طلبك الأول": "Post your first request",
    "{count} رد": "{count} replies",
    # ---- help requests ----
    "وش يحتاج جيرانك اليوم؟": "What do your neighbors need today?",
    "{count} طلب مفتوح · الأحدث أولاً": "{count} open requests · newest first",
    "الحي هادئ اليوم، لا توجد طلبات مساعدة حالياً.": "The neighborhood is quiet today. There are no help requests right now.",
    "كن أول من ينشر طلباً": "Be the first to post a request",
    "طلب مساعدة جديد": "New help request",
    "سيظهر طلبك لجيرانك في نفس الحي فقط.": "Your request is shown only to neighbors in the same neighborhood.",
    "العنوان": "Title",
    "مثال: أحتاج سلّم لمدة ساعة": "Example: I need a ladder for an hour",
    "التصنيف": "Category",
    "اختر التصنيف": "Choose a category",
    "الوصف": "Description",
    "نشر الطلب": "Post request",
    "كل الطلبات": "All requests",
    "تم الحل": "Resolved",
    "مفتوح": "Open",
    "تم الحل · إغلاق الطلب": "Resolved · close request",
    "ردود الجيران ({count})": "Neighbors' replies ({count})",
    "صاحب الطلب": "Request owner",
    "لا توجد ردود بعد. كن أول جار يرد.": "No replies yet. Be the first neighbor to reply.",
    "ردك": "Your reply",
    "اعرض مساعدتك أو اسأل عن التفاصيل": "Offer your help or ask for details",
    "إرسال الرد": "Send reply",
    "العنوان مطلوب.": "Title is required.",
    "اختر التصنيف من القائمة.": "Choose a category from the list.",
    "الوصف مطلوب.": "Description is required.",
    "تم نشر طلبك.": "Your request has been posted.",
    "لا يمكن الرد على طلب منتهٍ.": "You can't reply to a closed request.",
    "لا يمكن إرسال رد فارغ.": "A reply can't be empty.",
    "تم إغلاق طلبك كـ \"تم الحل\". شكراً لجيرانك!": "Your request was closed as resolved. Thanks to your neighbors!",
    # ---- membership ----
    "الخطوة 1 من 3": "Step 1 of 3",
    "الخطوة 2 من 3": "Step 2 of 3",
    "الخطوة 3 من 3": "Step 3 of 3",
    "طلب انضمام للحي": "Join request",
    "سيراجع عمدة الحي طلبك. جوالك وعنوانك لا يظهران لبقية السكان.": "The Omda will review your request. Your phone and address are not shown to other residents.",
    "الاسم": "Name",
    "رقم الجوال": "Phone number",
    "الحي": "Neighborhood",
    "اختر الحي": "Choose a neighborhood",
    "الشارع ورقم المنزل": "Street and house number",
    "إرسال الطلب": "Send request",
    "الاسم مطلوب.": "Name is required.",
    "رقم الجوال مطلوب.": "Phone number is required.",
    "رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام.": "The phone number must start with 05 and have 10 digits.",
    "العنوان مطلوب.": "Address is required.",
    "اختر الحي من القائمة.": "Choose a neighborhood from the list.",
    "تم إرسال طلبك": "Your request was sent",
    "رقم طلبك": "Your request number",
    "احتفظ برقم الطلب. ستحتاجه مع رقم جوالك لمتابعة حالة الطلب.": "Keep this number. You will need it with your phone number to track your request.",
    "متابعة الطلب": "Track request",
    "متابعة طلب الانضمام": "Track your join request",
    "أدخل رقم الطلب ورقم الجوال الذي استخدمته.": "Enter your request number and the phone number you used.",
    "رقم الطلب": "Request number",
    "رقم الجوال المستخدم في الطلب": "Phone number used in the request",
    "تحقق": "Check",
    "لم نجد طلباً بهذه البيانات. تأكد من رقم الطلب ورقم الجوال.": "We couldn't find a request with these details. Check the request number and phone number.",
    "قيد المراجعة": "Under review",
    "طلبك للانضمام إلى حي {hood} قيد المراجعة من مشرف الحي.": "Your request to join {hood} is being reviewed by the Omda.",
    "مرفوض": "Rejected",
    "سبب الرفض:": "Reason:",
    "مقبول": "Approved",
    "حياك الله في حي {hood}": "Welcome to {hood}",
    "تم استخدام كود الدعوة وإنشاء الحساب. يمكنك تسجيل الدخول.": "The invitation code has been used and the account created. You can log in.",
    "مفتاحك للحي · كود الدعوة (يُستخدم مرة واحدة):": "Your key to the neighborhood · invitation code (single use):",
    "سجّل الآن": "Register now",
    # ---- admin ----
    "مجلس العمدة": "Omda's office",
    "طلب انضمام ينتظر قرارك": "join requests awaiting your decision",
    "ساكن مسجّل في الحي": "registered residents",
    "طلب مساعدة مفتوح": "open help requests",
    "طلبات الانضمام الجديدة": "New join requests",
    "لا أحد يطرق الباب الآن. لا توجد طلبات انضمام جديدة.": "Nobody is knocking right now. There are no new join requests.",
    "الجوال": "Phone",
    "تاريخ الطلب": "Requested on",
    "رسالة ترحيب (اختياري)": "Welcome message (optional)",
    "مثال: أهلاً بك جاراً عزيزاً في حينا": "Example: Welcome to our neighborhood!",
    "قبول وإنشاء كود": "Approve and create code",
    "سبب الرفض (مطلوب عند الرفض)": "Rejection reason (required to reject)",
    "رفض": "Reject",
    "آخر القرارات": "Latest decisions",
    "الطلب": "Request",
    "القرار": "Decision",
    "الكود": "Code",
    "مُستخدم": "used",
    "تم اتخاذ قرار في هذا الطلب مسبقاً.": "A decision was already made on this request.",
    "تم قبول طلب {name}. كود الدعوة: {code} (يظهر للمتقدم في صفحة متابعة الطلب).": "{name}'s request was approved. Invitation code: {code} (shown to the applicant on the request-status page).",
    "لا يمكن الرفض بدون كتابة السبب.": "You can't reject without a reason.",
    "تم رفض طلب {name}.": "{name}'s request was rejected.",
    # ---- auth ----
    "أهلاً بعودتك": "Welcome back",
    "للسكان وعمدة الحي.": "For residents and the Omda.",
    "كلمة المرور": "Password",
    "دخول": "Log in",
    "ليس لديك حساب؟": "No account yet?",
    "اطلب الانضمام": "Request to join",
    "أو": "or",
    "تابع طلبك": "track your request",
    "رقم الجوال أو كلمة المرور غير صحيحة.": "The phone number or password is incorrect.",
    "تم تسجيل الخروج.": "You have logged out.",
    "الرجاء تسجيل الدخول أولاً.": "Please log in first.",
    "استخدم كود الدعوة الذي ظهر لك في صفحة متابعة الطلب.": "Use the invitation code shown on your request-status page.",
    "كود الدعوة": "Invitation code",
    "رقم الجوال (نفس رقم طلب الانضمام)": "Phone number (same as in the join request)",
    "4 أحرف على الأقل": "At least 4 letters",
    "رمز واحد على الأقل مثل @ أو #": "At least 1 symbol such as @ or #",
    "3 أرقام على الأقل": "At least 3 numbers",
    "تأكيد كلمة المرور": "Confirm password",
    "إنشاء الحساب": "Create account",
    "كود الدعوة مطلوب.": "Invitation code is required.",
    "كود الدعوة غير صحيح.": "Invalid invitation code.",
    "كود الدعوة مستخدم من قبل.": "This invitation code has already been used.",
    "رقم الجوال يجب أن يطابق الرقم المكتوب في طلب الانضمام.": "The phone number must match the one in your join request.",
    "رقم الجوال مسجل مسبقاً.": "This phone number is already registered.",
    "كلمة المرور يجب أن تحتوي على: {items}.": "The password must contain: {items}.",
    "كلمتا المرور غير متطابقتين.": "The passwords do not match.",
    "تم إنشاء حسابك بنجاح. سجّل دخولك الآن.": "Your account was created. Please log in.",
    "قوة كلمة المرور:": "Password strength:",
    "ضعيفة": "Weak",
    "قوية": "Strong",
    "قوية جداً": "Very strong",
    # ---- account ----
    "معلومات الحساب": "Account information",
    "تعديل المعلومات": "Edit information",
    "الدور": "Role",
    "عضو منذ": "Member since",
    "حفظ التعديلات": "Save changes",
    "تم حفظ معلوماتك.": "Your information was saved.",
    "تغيير كلمة المرور": "Change password",
    "كلمة المرور الحالية": "Current password",
    "كلمة المرور الجديدة": "New password",
    "تحديث كلمة المرور": "Update password",
    "كلمة المرور الحالية غير صحيحة.": "The current password is incorrect.",
    "تم تغيير كلمة المرور.": "Your password was changed.",
    "الحي لا يتغير من هنا. تواصل مع عمدة الحي.": "The neighborhood can't be changed here. Contact the Omda.",
    "يُستخدم رقم الجوال لتسجيل الدخول.": "Your phone number is used to log in.",
    # ---- neighbors ----
    "أعضاء حي {hood}": "Members of {hood}",
    "{count} عضو · {active} نشط الآن": "{count} members · {active} active now",
    "نشط الآن": "Active now",
    "غير نشط": "Offline",
    "طلبه الحالي": "Current request",
    "لا يوجد طلب مفتوح": "No open request",
    "أنت": "You",
    "لا يظهر رقم الجوال والعنوان لحماية خصوصية السكان.": "Phone numbers and addresses are hidden to protect residents' privacy.",
    # ---- notifications ----
    "مرحباً بك في حي {hood}! يمكنك الآن طلب المساعدة أو مساعدة جيرانك.": "Welcome to {hood}! You can now ask for help or help your neighbors.",
    "طلب انضمام جديد من {name}.": "New join request from {name}.",
    "{name} نشر طلب مساعدة: {title}": "{name} posted a help request: {title}",
    "{name} ردّ على طلبك: {title}": "{name} replied to your request: {title}",
    "{name} ردّ في الطلب: {title}": "{name} replied on: {title}",
    "تم حل الطلب «{title}». شكراً لمساعدتك!": "“{title}” was resolved. Thank you for helping!",
    # ---- errors ----
    "غير مسموح": "Not allowed",
    "ليس لديك صلاحية للوصول إلى هذه الصفحة.": "You don't have permission to open this page.",
    "غير موجود": "Not found",
    "الصفحة أو الطلب غير موجود.": "The page or request doesn't exist.",
    "طلب غير صالح": "Invalid request",
    "انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى.": "The form expired. Refresh the page and try again.",
    "العودة للرئيسية": "Back to home",
}
