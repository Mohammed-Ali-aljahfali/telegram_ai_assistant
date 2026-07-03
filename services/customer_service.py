"""services/customer_service.py — خدمة إدارة العملاء"""
from typing import Optional
from database.repositories.customer_repository import CustomerRepository
from models.customer import Customer, CustomerStatus
from infrastructure.logger import get_logger

logger = get_logger("customer_service")


class CustomerService:

    def __init__(self):
        self.repo = CustomerRepository()

    async def get_or_create(self, bot_user_id: int, telegram_id: int,
                             username: str = None, first_name: str = None,
                             last_name: str = None) -> Customer:
        customer = Customer(
            bot_user_id=bot_user_id,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        return await self.repo.create_or_update(customer)

    async def get(self, bot_user_id: int, telegram_id: int) -> Optional[Customer]:
        return await self.repo.get_by_telegram_id(bot_user_id, telegram_id)

    async def get_by_id(self, customer_id: int) -> Optional[Customer]:
        return await self.repo.get_by_id(customer_id)

    async def get_paginated(self, bot_user_id: int, page: int = 1, per_page: int = 10,
                             status: Optional[str] = None, search: Optional[str] = None
                             ) -> tuple[list[Customer], int]:
        customers = await self.repo.get_all_for_user(bot_user_id, page, per_page, status, search)
        total = await self.repo.count_for_user(bot_user_id, status)
        return customers, total

    async def update_status(self, customer_id: int, status: CustomerStatus):
        await self.repo.update_status(customer_id, status)

    async def update_interest(self, customer_id: int, score: float):
        await self.repo.update_interest_score(customer_id, score)

    async def update_summary(self, customer_id: int, summary: str):
        await self.repo.update_summary(customer_id, summary)

    async def update_service_type(self, customer_id: int, service_type: str):
        await self.repo.update_service_type(customer_id, service_type)

    async def add_note(self, customer_id: int, note: str):
        await self.repo.add_note(customer_id, note)

    async def get_new_today(self, bot_user_id: int) -> int:
        return await self.repo.get_new_today(bot_user_id)
