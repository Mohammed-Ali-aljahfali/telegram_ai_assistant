"""infrastructure/scheduler.py — جدولة المهام"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
from typing import Callable
from infrastructure.logger import get_logger

logger = get_logger("scheduler")


class TaskScheduler:
    """مجدول المهام باستخدام APScheduler"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone="Asia/Riyadh")

    def start(self):
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("✅ مجدول المهام بدأ")

    def stop(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("🛑 مجدول المهام توقف")

    def add_interval_job(self, func: Callable, seconds: int, job_id: str, **kwargs):
        self._scheduler.add_job(
            func, IntervalTrigger(seconds=seconds),
            id=job_id, replace_existing=True,
            kwargs=kwargs
        )
        logger.info(f"✅ مهمة دورية: {job_id} كل {seconds}s")

    def add_cron_job(self, func: Callable, hour: int, minute: int, job_id: str, **kwargs):
        self._scheduler.add_job(
            func, CronTrigger(hour=hour, minute=minute),
            id=job_id, replace_existing=True,
            kwargs=kwargs
        )
        logger.info(f"✅ مهمة يومية: {job_id} في {hour:02d}:{minute:02d}")

    def add_one_time_job(self, func: Callable, run_at: datetime, job_id: str, **kwargs):
        self._scheduler.add_job(
            func, DateTrigger(run_date=run_at),
            id=job_id, replace_existing=True,
            kwargs=kwargs
        )

    def remove_job(self, job_id: str):
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def pause_job(self, job_id: str):
        self._scheduler.pause_job(job_id)

    def resume_job(self, job_id: str):
        self._scheduler.resume_job(job_id)

    @property
    def running(self) -> bool:
        return self._scheduler.running


task_scheduler = TaskScheduler()
