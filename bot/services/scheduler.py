"""
ThroneChat — Scheduler Service
APScheduler configuration and job management.
Provides a global scheduler instance used by handlers to schedule one-off jobs.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from aiogram import Bot

from config.config import BATTLE_RESOLVE_MINUTES

logger = logging.getLogger(__name__)

# Global scheduler instance — initialized once, used everywhere
scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Configure recurring jobs and start the scheduler.
    Called once from bot/main.py at startup.
    """
    from bot.services.economy import economy_tick, daily_tick

    # Hourly economy tick — every hour at :00
    scheduler.add_job(
        economy_tick,
        trigger=IntervalTrigger(hours=1),
        args=[bot],
        id="economy_tick",
        name="💰 Hourly Economy Tick",
        replace_existing=True,
    )

    # Daily tick — every day at 12:00 UTC
    scheduler.add_job(
        daily_tick,
        trigger=CronTrigger(hour=12, minute=0),
        args=[bot],
        id="daily_tick",
        name="📅 Daily Tick (IP + Events)",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("⏰ APScheduler started with %d jobs", len(scheduler.get_jobs()))

    return scheduler


def schedule_battle_resolution(battle_id: int, bot: Bot) -> None:
    """
    Schedule a one-off job to resolve a battle after BATTLE_RESOLVE_MINUTES.
    Called from the /attack handler when a battle is created.
    """
    from bot.services.battle import resolve_battle

    run_date = datetime.utcnow() + timedelta(minutes=BATTLE_RESOLVE_MINUTES)

    scheduler.add_job(
        resolve_battle,
        trigger=DateTrigger(run_date=run_date),
        args=[battle_id, bot],
        id=f"battle_{battle_id}",
        name=f"⚔️ Resolve Battle #{battle_id}",
        replace_existing=True,
    )

    logger.info(
        "Scheduled battle %d resolution at %s (%d min)",
        battle_id, run_date.isoformat(), BATTLE_RESOLVE_MINUTES,
    )


def schedule_conspiracy_resolution(
    conspiracy_id: int, expires_at: datetime, bot: Bot
) -> None:
    """
    Schedule a one-off job to resolve a conspiracy at its expiry time.
    Called when a conspiracy is created.
    """
    # Import here to avoid circular imports
    from bot.services.conspiracy import resolve_conspiracy

    scheduler.add_job(
        resolve_conspiracy,
        trigger=DateTrigger(run_date=expires_at),
        args=[conspiracy_id, bot],
        id=f"conspiracy_{conspiracy_id}",
        name=f"🗡️ Resolve Conspiracy #{conspiracy_id}",
        replace_existing=True,
    )

    logger.info(
        "Conspiracy %d resolution scheduled at %s",
        conspiracy_id, expires_at.isoformat(),
    )
