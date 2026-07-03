"""services/statistics_service.py — خدمة الإحصائيات"""
from datetime import date, timedelta
from database.repositories.statistics_repository import StatisticsRepository
from database.repositories.customer_repository import CustomerRepository
from infrastructure.logger import get_logger

logger = get_logger("statistics_service")


class StatisticsService:

    def __init__(self):
        self.stats_repo = StatisticsRepository()
        self.customer_repo = CustomerRepository()

    async def record_message_received(self, bot_user_id: int):
        await self.stats_repo.increment(bot_user_id, "messages_received")

    async def record_message_sent(self, bot_user_id: int):
        await self.stats_repo.increment(bot_user_id, "messages_sent")

    async def record_new_customer(self, bot_user_id: int):
        await self.stats_repo.increment(bot_user_id, "new_customers")

    async def record_ai_response(self, bot_user_id: int):
        await self.stats_repo.increment(bot_user_id, "ai_responses")

    async def record_conversion(self, bot_user_id: int):
        await self.stats_repo.increment(bot_user_id, "conversions")

    async def get_dashboard(self, bot_user_id: int) -> dict:
        today = await self.stats_repo.get_today(bot_user_id)
        weekly = await self.stats_repo.get_period(bot_user_id, 7)
        monthly = await self.stats_repo.get_period(bot_user_id, 30)
        total_customers = await self.customer_repo.count_for_user(bot_user_id)
        new_today = await self.customer_repo.get_new_today(bot_user_id)
        return {
            "today": today,
            "weekly": weekly,
            "monthly": monthly,
            "total_customers": total_customers,
            "new_customers_today": new_today,
        }

    async def get_period_stats(self, bot_user_id: int, days: int) -> dict:
        return await self.stats_repo.get_period(bot_user_id, days)
