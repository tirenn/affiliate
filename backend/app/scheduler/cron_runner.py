import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models import Product, SystemSetting, CommentedThread
from app.agent.threads_agent import ThreadsAgentRunner, get_system_setting

logger = logging.getLogger("threads_agent.scheduler")


class ThreadsCronScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.lock = asyncio.Lock()
        self.is_currently_posting = False
        self.job_id = "threads_affiliate_cron"

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started.")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped.")

    async def reload_schedule(self):
        """Reload window and posts count from DB settings and update job interval"""
        async with AsyncSessionLocal() as db:
            enabled_str = await get_system_setting(db, "scheduler_enabled", "false")
            enabled = enabled_str.lower() == "true"
            
            window_str = await get_system_setting(db, "scheduler_window_minutes", "60")
            posts_str = await get_system_setting(db, "scheduler_posts_per_window", "10")
            
            window_min = int(window_str) if window_str.isdigit() else 60
            posts_count = max(int(posts_str) if posts_str.isdigit() else 10, 1)
            
            # Hitung interval: misal 60 menit / 10 post = setiap 6 menit
            interval_minutes = max(round(window_min / posts_count, 2), 0.5)

        # Hapus job lama jika ada
        if self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)

        if enabled:
            self.scheduler.add_job(
                self._cron_tick,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id=self.job_id,
                name="Threads Viral Affiliate Auto Poster",
                replace_existing=True
            )
            logger.info(f"Cron aktif: Memposting setiap {interval_minutes} menit ({posts_count} post per {window_min} menit)")
        else:
            logger.info("Cron scheduler dinonaktifkan di pengaturan.")

    async def _cron_tick(self):
        """Internal tick dipanggil oleh APScheduler"""
        # Sedikit anti-spam jitter delay (1-30 detik)
        delay_sec = random.randint(1, 30)
        logger.info(f"Menerapkan anti-spam jitter delay: {delay_sec}s")
        await asyncio.sleep(delay_sec)

        await self.trigger_next_product()

    async def trigger_next_product(self) -> Optional[int]:
        """Menjalankan siklus auto-comment Threads"""
        if self.lock.locked() or self.is_currently_posting:
            logger.warning("Posting job lain sedang berjalan. Melewati tick ini.")
            return None

        async with self.lock:
            self.is_currently_posting = True
            try:
                async with AsyncSessionLocal() as db:
                    runner = ThreadsAgentRunner(db)
                    result = await runner.execute()
                    logger.info(f"Eksekusi agen selesai. Status: {result.get('status')}")
                    return result.get("post_log_id")

            except Exception as e:
                logger.error(f"Error pada eksekusi scheduler: {e}", exc_info=True)
                return None
            finally:
                self.is_currently_posting = False

    async def get_status(self) -> dict:
        """Informasi status scheduler terkini"""
        async with AsyncSessionLocal() as db:
            enabled_str = await get_system_setting(db, "scheduler_enabled", "false")
            enabled = enabled_str.lower() == "true"
            
            window_str = await get_system_setting(db, "scheduler_window_minutes", "60")
            posts_str = await get_system_setting(db, "scheduler_posts_per_window", "10")
            
            window_min = int(window_str) if window_str.isdigit() else 60
            posts_count = max(int(posts_str) if posts_str.isdigit() else 10, 1)
            calc_interval = round(window_min / posts_count, 2)

            total_prods = (await db.execute(select(func.count(Product.id)))).scalar_one()
            unposted_prods = (await db.execute(select(func.count(Product.id)).where(Product.is_posted == False))).scalar_one()
            commented_threads = (await db.execute(select(func.count(CommentedThread.id)))).scalar_one()

        job = self.scheduler.get_job(self.job_id) if self.scheduler.running else None
        next_run = job.next_run_time if job else None

        return {
            "is_running": self.scheduler.running,
            "scheduler_enabled": enabled,
            "interval_minutes": calc_interval,
            "window_minutes": window_min,
            "posts_per_window": posts_count,
            "next_run_time": next_run,
            "total_products_count": total_prods,
            "unposted_products_count": unposted_prods,
            "commented_threads_count": commented_threads,
            "is_currently_posting": self.is_currently_posting
        }


cron_scheduler = ThreadsCronScheduler()
