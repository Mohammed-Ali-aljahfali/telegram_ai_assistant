"""database/connection.py — إدارة الاتصال بـ SQLite"""
import aiosqlite
import asyncio
from pathlib import Path
from typing import Any, Optional
from contextlib import asynccontextmanager
from config import config
from infrastructure.logger import get_logger

logger = get_logger("database")


class DatabaseManager:
    """مدير قاعدة البيانات (Singleton)"""
    _instance: Optional["DatabaseManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self):
        """تهيئة قاعدة البيانات وتشغيل Migrations"""
        if self._initialized:
            return
        config.create_directories()
        self._db_path = str(config.DATABASE_PATH)
        await self._run_migrations()
        self._initialized = True
        logger.info(f"✅ قاعدة البيانات جاهزة: {self._db_path}")

    @asynccontextmanager
    async def get_connection(self):
        """سياق اتصال بقاعدة البيانات"""
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA cache_size=10000")
            yield conn

    async def execute(self, query: str, params: tuple = ()) -> int:
        """تنفيذ استعلام INSERT/UPDATE/DELETE وإرجاع lastrowid"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.lastrowid

    async def execute_many(self, query: str, params_list: list[tuple]):
        """تنفيذ استعلامات متعددة"""
        async with self.get_connection() as conn:
            await conn.executemany(query, params_list)
            await conn.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        """جلب صف واحد"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """جلب جميع الصفوف"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchall()

    async def _run_migrations(self):
        """تشغيل Migrations"""
        from database.migrations import run_migrations
        await run_migrations(self._db_path)

    async def close(self):
        """إغلاق الاتصال"""
        self._initialized = False
        logger.info("🔒 قاعدة البيانات أُغلقت")


def get_db() -> DatabaseManager:
    """الحصول على مثيل DatabaseManager"""
    return DatabaseManager()
