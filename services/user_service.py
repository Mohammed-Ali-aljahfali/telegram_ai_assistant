"""services/user_service.py — خدمة مستخدمي البوت"""
from typing import Optional
from config import config
from database.repositories.user_repository import UserRepository
from models.user import BotUser, UserRole, UserStatus
from infrastructure.logger import get_logger

logger = get_logger("user_service")


class UserService:

    def __init__(self):
        self.repo = UserRepository()

    async def get_or_create(self, telegram_id: int, username: str = None,
                            first_name: str = None) -> BotUser:
        user = await self.repo.get_by_telegram_id(telegram_id)
        if not user:
            role = UserRole.DEVELOPER if telegram_id == config.DEVELOPER_ID else UserRole.USER
            user = BotUser(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                role=role,
            )
            await self.repo.create(user)
            user = await self.repo.get_by_telegram_id(telegram_id)
            logger.info(f"✅ مستخدم جديد: {telegram_id} ({role})")
        else:
            await self.repo.update_last_active(telegram_id)
        return user

    async def get(self, telegram_id: int) -> Optional[BotUser]:
        return await self.repo.get_by_telegram_id(telegram_id)

    async def get_all(self, page: int = 1, per_page: int = 15) -> tuple[list[BotUser], int]:
        users = await self.repo.get_all(page, per_page)
        total = await self.repo.count_all()
        return users, total

    async def update_status(self, telegram_id: int, status: UserStatus):
        await self.repo.update_status(telegram_id, status)

    async def set_role(self, telegram_id: int, role: UserRole):
        await self.repo.update_role(telegram_id, role)

    async def ban(self, telegram_id: int):
        await self.repo.update_status(telegram_id, UserStatus.BANNED)

    async def unban(self, telegram_id: int):
        await self.repo.update_status(telegram_id, UserStatus.ACTIVE)

    async def suspend(self, telegram_id: int):
        await self.repo.update_status(telegram_id, UserStatus.SUSPENDED)

    async def delete(self, telegram_id: int):
        await self.repo.delete(telegram_id)

    async def is_developer(self, telegram_id: int) -> bool:
        if telegram_id == config.DEVELOPER_ID:
            return True
        user = await self.repo.get_by_telegram_id(telegram_id)
        return user is not None and user.role == UserRole.DEVELOPER

    async def is_banned(self, telegram_id: int) -> bool:
        user = await self.repo.get_by_telegram_id(telegram_id)
        return user is not None and user.status == UserStatus.BANNED

    async def is_suspended(self, telegram_id: int) -> bool:
        user = await self.repo.get_by_telegram_id(telegram_id)
        return user is not None and user.status == UserStatus.SUSPENDED

    async def save_session(self, telegram_id: int, session: str):
        await self.repo.update_session(telegram_id, session, True)

    async def clear_session(self, telegram_id: int):
        await self.repo.update_session(telegram_id, None, False)

    async def update_phone(self, telegram_id: int, phone: str):
        await self.repo.update_phone(telegram_id, phone)
