"""bot/messages/templates.py — قوالب الرسائل"""
from datetime import datetime


WELCOME_NEW = """🤖 *مرحباً بك في المساعد الذكي لـ Telegram*

المبرمج حمزه المطري يبلغك تحياته 🫡

أنا نظام ذكي متكامل يساعدك على:
• 📨 مراقبة وإدارة رسائل عملائك تلقائياً
• 🤖 الرد الذكي باستخدام الذكاء الاصطناعي
• 📊 تحليل بيانات العملاء والمحادثات
• 📡 مراقبة القنوات والمجموعات

للبدء، تحتاج إلى *تسجيل الدخول* بحسابك على Telegram.
"""

WELCOME_BACK = """🏠 *أهلاً بعودتك، {}!*

المبرمج حمزه المطري يبلغك تحياته 🫡

لوحة التحكم الرئيسية جاهزة. اختر ما تريد:
"""

LOGIN_PHONE_PROMPT = """📱 *تسجيل الدخول*

أرسل رقم جوالك مع رمز الدولة، مثال:
`+966501234567`

أو اضغط الزر أدناه لمشاركة رقمك تلقائياً 👇
"""

LOGIN_CODE_PROMPT = """🔑 *أدخل رمز التحقق*

تم إرسال رمز مكون من 5 أرقام إلى تطبيق Telegram الخاص بك.
أدخل الرمز هنا:

⚠️ _لا تشارك هذا الرمز مع أي شخص_
"""

LOGIN_2FA_PROMPT = """🔒 *التحقق بخطوتين*

حسابك محمي بكلمة مرور إضافية.
أدخل كلمة المرور:

⚠️ _كلمة المرور لن تُحفظ، تُستخدم مرة واحدة فقط_
"""

SUBSCRIPTION_REQUIRED = """📢 *الاشتراك الإجباري*

للمتابعة، يجب الاشتراك في القنوات التالية:

{}

بعد الاشتراك، اضغط على زر التحقق 👇
"""

BANNED_MESSAGE = "🚫 حسابك محظور من استخدام هذا البوت."
SUSPENDED_MESSAGE = "⏸️ حسابك موقوف مؤقتاً. تواصل مع الدعم."

# ─── رسائل تدفق تسجيل الدخول ────────────────────────────────────────────────
LOGIN_CODE_EXPIRED = """⏰ *انتهت صلاحية رمز التحقق*

للحصول على رمز جديد، اضغط على زر إعادة الإرسال أدناه.
"""

LOGIN_CODE_INVALID = """❌ *رمز غير صحيح*

تأكد من إدخال الرمز كاملاً دون مسافات، مثال: `12345`
المتبقي: {} محاولة
"""

LOGIN_CODE_RESENT = """🔄 *تم إرسال رمز تحقق جديد*

⚠️ _الرمز السابق أصبح غير صالح._
أدخل الرمز الجديد من Telegram:
"""

LOGIN_FLOOD_WAIT = """⏳ *تنبيه من Telegram*

طلبات كثيرة جداً. انتظر *{} ثانية* ثم حاول مجدداً.
"""

LOGIN_2FA_WRONG = """❌ *كلمة مرور 2FA غير صحيحة*

تأكد من كلمة المرور وحاول مجدداً.
إذا نسيت كلمة المرور، راجع إعدادات Telegram ← الخصوصية ← جدران الحماية.
"""

LOGIN_MAX_ATTEMPTS = """🚫 *تجاوزت الحد الأقصى للمحاولات*

لأسباب أمنية، توقفت عملية تسجيل الدخول.
اضغط على زر تسجيل الدخول للبدء من جديد.
"""

LOGIN_AUTH_RESTART = """🔄 *انتهت جلسة المصادقة*

حدث خطأ داخلي في Telegram.
أدخل رقم الهاتف مجدداً للبدء.
"""


def format_stats_card(stats: dict, period: str = "اليوم") -> str:
    today = stats.get("today", {})
    return f"""📊 *إحصائيات {period}*

📨 الرسائل الواردة: `{today.get('messages_received', 0)}`
📤 الرسائل المرسلة: `{today.get('messages_sent', 0)}`
🆕 عملاء جدد: `{today.get('new_customers', 0)}`
🤖 ردود AI: `{today.get('ai_responses', 0)}`
✅ تحويلات: `{today.get('conversions', 0)}`
👥 إجمالي العملاء: `{stats.get('total_customers', 0)}`
"""


def format_customer_card(customer) -> str:
    return f"""👤 *{customer.display_name}*

🆔 ID: `{customer.telegram_id}`
📱 Username: `@{customer.username or 'غير محدد'}`
📊 الحالة: {customer.status_emoji} {customer.status.value}
⭐ الاهتمام: `{customer.interest_score:.1f}/10`
🛠️ الخدمة: `{customer.service_type or 'غير محدد'}`
💬 الرسائل: `{customer.message_count}`
📅 آخر تواصل: `{customer.last_contact.strftime('%Y-%m-%d %H:%M') if customer.last_contact else 'غير محدد'}`
"""


def format_system_status(connected_count: int, ai_status: str, db_size: str) -> str:
    return f"""🖥️ *حالة النظام*

🔗 حسابات Telethon النشطة: `{connected_count}`
🤖 الذكاء الاصطناعي: `{ai_status}`
💾 حجم قاعدة البيانات: `{db_size}`
⏰ الوقت: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
"""


def format_notification(notif: dict) -> str:
    icons = {
        "new_customer": "👤",
        "keyword": "🔑",
        "system": "⚙️",
        "summary": "📊",
        "alert": "🚨",
    }
    icon = icons.get(notif.get("type", "system"), "🔔")
    status = "✅" if notif.get("is_read") else "🔵"
    return f"{status} {icon} *{notif.get('title', '')}*\n{notif.get('content', '')}"
