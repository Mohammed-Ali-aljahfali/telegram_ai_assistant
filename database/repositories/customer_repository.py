"""database/repositories/customer_repository.py — مستودع العملاء"""
from datetime import datetime
from typing import Optional
from database.connection import get_db
from models.customer import Customer, CustomerStatus
from infrastructure.logger import get_logger

logger = get_logger("customer_repo")


class CustomerRepository:

    def __init__(self):
        self.db = get_db()

    async def create_or_update(self, customer: Customer) -> Customer:
        existing = await self.get_by_telegram_id(customer.bot_user_id, customer.telegram_id)
        if existing:
            await self.db.execute(
                """UPDATE customers SET username=?, first_name=?, last_name=?,
                   last_contact=?, message_count=message_count+1
                   WHERE bot_user_id=? AND telegram_id=?""",
                (customer.username, customer.first_name, customer.last_name,
                 datetime.now(), customer.bot_user_id, customer.telegram_id)
            )
            existing.message_count += 1
            return existing
        uid = await self.db.execute(
            """INSERT INTO customers
               (bot_user_id, telegram_id, username, first_name, last_name,
                phone, country, language, status, interest_score, service_type,
                first_contact, last_contact, message_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (customer.bot_user_id, customer.telegram_id, customer.username,
             customer.first_name, customer.last_name, customer.phone,
             customer.country, customer.language, customer.status.value,
             customer.interest_score, customer.service_type,
             datetime.now(), datetime.now(), 1)
        )
        customer.id = uid
        return customer

    async def get_by_telegram_id(self, bot_user_id: int, telegram_id: int) -> Optional[Customer]:
        row = await self.db.fetchone(
            "SELECT * FROM customers WHERE bot_user_id=? AND telegram_id=?",
            (bot_user_id, telegram_id)
        )
        return self._row_to_model(row) if row else None

    async def get_by_id(self, customer_id: int) -> Optional[Customer]:
        row = await self.db.fetchone("SELECT * FROM customers WHERE id=?", (customer_id,))
        return self._row_to_model(row) if row else None

    async def get_all_for_user(
        self, bot_user_id: int, page: int = 1, per_page: int = 10,
        status: Optional[str] = None, search: Optional[str] = None
    ) -> list[Customer]:
        conditions = ["bot_user_id=?"]
        params: list = [bot_user_id]
        if status:
            conditions.append("status=?")
            params.append(status)
        if search:
            conditions.append("(first_name LIKE ? OR username LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " AND ".join(conditions)
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        rows = await self.db.fetchall(
            f"SELECT * FROM customers WHERE {where} ORDER BY last_contact DESC LIMIT ? OFFSET ?",
            tuple(params)
        )
        return [self._row_to_model(r) for r in rows]

    async def count_for_user(self, bot_user_id: int, status: Optional[str] = None) -> int:
        if status:
            row = await self.db.fetchone(
                "SELECT COUNT(*) FROM customers WHERE bot_user_id=? AND status=?",
                (bot_user_id, status)
            )
        else:
            row = await self.db.fetchone(
                "SELECT COUNT(*) FROM customers WHERE bot_user_id=?", (bot_user_id,)
            )
        return row[0] if row else 0

    async def update_status(self, customer_id: int, status: CustomerStatus):
        await self.db.execute(
            "UPDATE customers SET status=? WHERE id=?",
            (status.value, customer_id)
        )

    async def update_interest_score(self, customer_id: int, score: float):
        await self.db.execute(
            "UPDATE customers SET interest_score=? WHERE id=?",
            (min(10.0, max(0.0, score)), customer_id)
        )

    async def update_summary(self, customer_id: int, summary: str):
        await self.db.execute(
            "UPDATE customers SET summary=? WHERE id=?", (summary, customer_id)
        )

    async def update_service_type(self, customer_id: int, service_type: str):
        await self.db.execute(
            "UPDATE customers SET service_type=? WHERE id=?",
            (service_type, customer_id)
        )

    async def add_note(self, customer_id: int, note: str):
        existing = await self.get_by_id(customer_id)
        old_notes = existing.notes or ""
        new_notes = f"{old_notes}\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {note}".strip()
        await self.db.execute(
            "UPDATE customers SET notes=? WHERE id=?", (new_notes, customer_id)
        )

    async def get_new_today(self, bot_user_id: int) -> int:
        row = await self.db.fetchone(
            "SELECT COUNT(*) FROM customers WHERE bot_user_id=? AND DATE(first_contact)=DATE('now')",
            (bot_user_id,)
        )
        return row[0] if row else 0

    def _row_to_model(self, row) -> Customer:
        d = dict(row)
        return Customer(**d)
