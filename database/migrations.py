"""database/migrations.py — إنشاء جداول قاعدة البيانات"""
import aiosqlite
from infrastructure.logger import get_logger

logger = get_logger("migrations")

SCHEMA_VERSION = 1

MIGRATIONS = [
    # Migration 1: الإنشاء الأولي
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bot_users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id     INTEGER UNIQUE NOT NULL,
        username        TEXT,
        first_name      TEXT,
        phone           TEXT,
        role            TEXT DEFAULT 'user',
        status          TEXT DEFAULT 'active',
        is_authenticated INTEGER DEFAULT 0,
        telethon_session TEXT,
        two_factor_hint TEXT,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_active     DATETIME,
        settings        TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS customers (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER NOT NULL,
        telegram_id     INTEGER NOT NULL,
        username        TEXT,
        first_name      TEXT,
        last_name       TEXT,
        phone           TEXT,
        country         TEXT,
        language        TEXT DEFAULT 'ar',
        status          TEXT DEFAULT 'new',
        interest_score  REAL DEFAULT 0.0,
        service_type    TEXT,
        notes           TEXT,
        first_contact   DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_contact    DATETIME,
        message_count   INTEGER DEFAULT 0,
        summary         TEXT,
        FOREIGN KEY (bot_user_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE,
        UNIQUE(bot_user_id, telegram_id)
    );

    CREATE TABLE IF NOT EXISTS chats (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER NOT NULL,
        customer_id     INTEGER,
        chat_id         INTEGER NOT NULL,
        chat_type       TEXT DEFAULT 'private',
        title           TEXT,
        username        TEXT,
        auto_reply      INTEGER DEFAULT 1,
        ai_enabled      INTEGER DEFAULT 1,
        status          TEXT DEFAULT 'active',
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_user_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        UNIQUE(bot_user_id, chat_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id         INTEGER NOT NULL,
        telegram_msg_id INTEGER,
        sender_id       INTEGER,
        sender_type     TEXT DEFAULT 'user',
        content         TEXT,
        message_type    TEXT DEFAULT 'text',
        intent          TEXT,
        sentiment       TEXT,
        is_important    INTEGER DEFAULT 0,
        ai_analyzed     INTEGER DEFAULT 0,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS monitored_channels (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER NOT NULL,
        channel_id      INTEGER NOT NULL,
        username        TEXT,
        title           TEXT,
        channel_type    TEXT DEFAULT 'channel',
        is_active       INTEGER DEFAULT 1,
        auto_reply      INTEGER DEFAULT 0,
        keywords_only   INTEGER DEFAULT 1,
        added_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_checked    DATETIME,
        FOREIGN KEY (bot_user_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE,
        UNIQUE(bot_user_id, channel_id)
    );

    CREATE TABLE IF NOT EXISTS required_channels (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id      INTEGER NOT NULL,
        channel_username TEXT,
        title           TEXT,
        channel_type    TEXT DEFAULT 'channel',
        is_active       INTEGER DEFAULT 1,
        added_by        INTEGER,
        added_at        DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS keywords (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER NOT NULL,
        keyword         TEXT NOT NULL,
        category        TEXT DEFAULT 'custom',
        action          TEXT DEFAULT 'alert',
        reply_template  TEXT,
        is_active       INTEGER DEFAULT 1,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_user_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ai_memory (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id     INTEGER NOT NULL,
        bot_user_id     INTEGER NOT NULL,
        memory_type     TEXT DEFAULT 'fact',
        content         TEXT NOT NULL,
        importance      REAL DEFAULT 0.5,
        expires_at      DATETIME,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS settings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER,
        key             TEXT NOT NULL,
        value           TEXT,
        value_type      TEXT DEFAULT 'string',
        category        TEXT DEFAULT 'general',
        description     TEXT,
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(bot_user_id, key)
    );

    CREATE TABLE IF NOT EXISTS logs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER,
        level           TEXT DEFAULT 'INFO',
        module          TEXT,
        action          TEXT,
        details         TEXT,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER NOT NULL,
        type            TEXT DEFAULT 'system',
        title           TEXT,
        content         TEXT,
        is_read         INTEGER DEFAULT 0,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_user_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER,
        task_type       TEXT,
        payload         TEXT DEFAULT '{}',
        status          TEXT DEFAULT 'pending',
        scheduled_at    DATETIME,
        executed_at     DATETIME,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS statistics (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id     INTEGER NOT NULL,
        date            DATE NOT NULL,
        messages_received INTEGER DEFAULT 0,
        messages_sent   INTEGER DEFAULT 0,
        new_customers   INTEGER DEFAULT 0,
        ai_responses    INTEGER DEFAULT 0,
        conversions     INTEGER DEFAULT 0,
        UNIQUE(bot_user_id, date)
    );

    CREATE INDEX IF NOT EXISTS idx_customers_bot_user ON customers(bot_user_id);
    CREATE INDEX IF NOT EXISTS idx_customers_telegram ON customers(telegram_id);
    CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);
    CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
    CREATE INDEX IF NOT EXISTS idx_messages_analyzed ON messages(ai_analyzed);
    CREATE INDEX IF NOT EXISTS idx_chats_bot_user ON chats(bot_user_id);
    CREATE INDEX IF NOT EXISTS idx_channels_bot_user ON monitored_channels(bot_user_id);
    CREATE INDEX IF NOT EXISTS idx_keywords_bot_user ON keywords(bot_user_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(bot_user_id, is_read);
    CREATE INDEX IF NOT EXISTS idx_stats_user_date ON statistics(bot_user_id, date);
    CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at);
    CREATE INDEX IF NOT EXISTS idx_ai_memory_customer ON ai_memory(customer_id);
    """
]


async def run_migrations(db_path: str):
    """تشغيل الـ migrations"""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")

        # إنشاء جدول الإصدار
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

        # جلب الإصدار الحالي
        cursor = await conn.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        current_version = row[0] or 0

        # تطبيق الـ migrations الجديدة
        for i, migration in enumerate(MIGRATIONS, start=1):
            if i > current_version:
                logger.info(f"🔄 تطبيق migration {i}...")
                for statement in migration.strip().split(";"):
                    stmt = statement.strip()
                    if stmt:
                        await conn.execute(stmt)
                await conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (i,)
                )
                await conn.commit()
                logger.info(f"✅ Migration {i} طُبِّق")

        logger.info(f"✅ قاعدة البيانات محدّثة (إصدار {len(MIGRATIONS)})")
