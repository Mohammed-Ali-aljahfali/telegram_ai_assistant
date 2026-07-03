# 🤖 المساعد الذكي لـ Telegram

نظام SaaS احترافي يحوّل حساب Telegram الشخصي إلى مساعد ذكي متكامل.

## ✨ المميزات

- 🤖 ردود تلقائية ذكية بالذكاء الاصطناعي (OpenAI / Gemini / Claude)
- 👥 إدارة العملاء الكاملة مع تتبع حالتهم
- 📡 مراقبة القنوات والمجموعات تلقائياً
- 🔑 كشف الكلمات المفتاحية وإرسال تنبيهات فورية
- 📢 نظام اشتراك إجباري قابل للتحكم
- 👑 لوحة تحكم المطور الكاملة
- 💾 نسخ احتياطي تلقائي يومي مع حماية البيانات من الفقدان

---

## 🚀 التشغيل المحلي

### 1. تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

### 2. إعداد ملف .env
```bash
cp .env.example .env
# عدّل القيم في .env
```

المتغيرات الضرورية:
```env
BOT_TOKEN=your_bot_token
API_ID=your_api_id
API_HASH=your_api_hash
DEVELOPER_ID=your_telegram_id
ENCRYPTION_KEY=<run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# للتطوير المحلي — اتركه فارغاً أو ./data
DATA_DIR=./data
```

### 3. تشغيل النظام
```bash
python main.py
```

---

## ☁️ النشر على Railway

### متطلبات النشر

يعتمد المشروع على **Railway Volumes** لحفظ البيانات بشكل دائم بين عمليات النشر.

### الخطوات

#### 1. إنشاء مشروع على Railway
```
railway.app → New Project → Deploy from GitHub Repo
```

#### 2. إضافة Volume لحفظ البيانات بشكل دائم

> ⚠️ **هذه الخطوة ضرورية** لمنع فقدان البيانات عند كل تحديث.

```
Railway Dashboard → مشروعك → Add Volume
    Mount Path: /data
```

#### 3. ضبط متغيرات البيئة

في Railway Dashboard → Variables → Add All:

```env
BOT_TOKEN=your_bot_token
API_ID=your_api_id
API_HASH=your_api_hash
DEVELOPER_ID=your_telegram_id
ENCRYPTION_KEY=your_fernet_key
DATA_DIR=/data
LOG_LEVEL=INFO
AI_PROVIDER=openai
OPENAI_API_KEY=optional
```

> 💡 `DATA_DIR=/data` يُخبر التطبيق بحفظ كل البيانات في Volume الدائم.

#### 4. النشر

```
railway up
# أو push إلى GitHub وسيتم النشر تلقائياً
```

#### 5. التحقق من النشر

```
railway logs
```

يجب أن ترى:
```
📂 مسارات التخزين الدائم:
   DATA_DIR    : /data
   DATABASE    : /data/database.db
   BACKUPS     : /data/backups
   SESSIONS    : /data/sessions
   LOGS        : /data/logs
✅ DATA_DIR جاهز للقراءة والكتابة
```

---

## 🔒 ضمان البيانات الدائمة

| المكوّن | الموقع على Railway | دائم؟ |
|---|---|---|
| قاعدة البيانات | `/data/database.db` | ✅ نعم (Volume) |
| جلسات Telethon | محفوظة في DB (مشفّرة) | ✅ نعم |
| النسخ الاحتياطية | `/data/backups/` | ✅ نعم (Volume) |
| السجلات | `/data/logs/` | ✅ نعم (Volume) |
| الكود | `/app/` | ♻️ يتجدد مع كل Deploy |

---

## 📱 كيفية الاستخدام

1. افتح البوت على Telegram
2. اضغط `/start`
3. اضغط **تسجيل الدخول**
4. أدخل رقم جوالك مع رمز الدولة
5. أدخل رمز التحقق المرسل لتيليجرام
6. أدخل كلمة مرور التحقق بخطوتين إن وجدت
7. انضم للقنوات المطلوبة (إن وُجدت)
8. استمتع بلوحة التحكم! 🎉

---

## 🏗️ هيكل المشروع

```
telegram_ai_assistant/
├── main.py                  # نقطة الدخول
├── config.py                # الإعدادات (جميع المسارات من DATA_DIR)
├── Procfile                 # أمر تشغيل Railway
├── railway.json             # إعدادات Railway
├── nixpacks.toml            # إعدادات البناء
├── .env.example             # قالب متغيرات البيئة
├── requirements.txt         # المتطلبات
├── core/                    # قلب التطبيق
├── bot/                     # بوت Telegram
├── telethon_client/         # عميل Telethon
├── ai/                      # طبقة الذكاء الاصطناعي
├── services/                # طبقة الخدمات
├── database/                # قاعدة البيانات والـ migrations
├── models/                  # نماذج البيانات
├── infrastructure/          # البنية التحتية (logger, startup_checks...)
└── utils/                   # أدوات مساعدة
```

---

## ⚙️ إعدادات المطور

- **الاشتراك الإجباري**: إضافة/حذف قنوات وتفعيل/تعطيل الميزة
- **إدارة المستخدمين**: إضافة، حذف، حظر، إيقاف، ترقية
- **النسخ الاحتياطي**: يومي تلقائي (3 صباحاً) + يدوي + تلقائي قبل كل Migration

---

## 🔐 الأمان

- تشفير الجلسات بـ Fernet
- Rate Limiting لكل مستخدم
- نظام صلاحيات ثلاثي (developer / admin / user)
- حماية من الحظر والإيقاف
- لا تُسجَّل كلمات المرور أو رموز التحقق في السجلات
