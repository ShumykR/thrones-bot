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

from config.config import (
    BATTLE_RESOLVE_MINUTES, 
    ECONOMY_INTERVAL_MINUTES, 
    DAILY_INTERVAL_MINUTES, 
    POLL_INTERVAL_MINUTES
)

logger = logging.getLogger(__name__)

# Global scheduler instance — initialized once, used everywhere
scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Configure recurring jobs and start the scheduler.
    Called once from bot/main.py at startup.
    """
    from bot.services.economy import economy_tick, daily_tick

    # Hourly economy tick
    scheduler.add_job(
        economy_tick,
        trigger=IntervalTrigger(minutes=ECONOMY_INTERVAL_MINUTES),
        args=[bot],
        id="economy_tick",
        name="💰 Hourly Economy Tick",
        replace_existing=True,
    )

    # Daily tick
    scheduler.add_job(
        daily_tick,
        trigger=IntervalTrigger(minutes=DAILY_INTERVAL_MINUTES),
        args=[bot],
        id="daily_tick",
        name="📅 Daily Tick (IP + Events)",
        replace_existing=True,
    )

    # Daily poll broadcast
    scheduler.add_job(
        broadcast_poll,
        trigger=IntervalTrigger(minutes=POLL_INTERVAL_MINUTES),
        args=[bot],
        id="poll_tick",
        name="📜 Daily Secret Poll",
        replace_existing=True,
    )

    scheduler.add_job(
        check_expired_conspiracies,
        trigger=IntervalTrigger(minutes=1),
        args=[bot],
        id="check_expired_conspiracies",
        name="🗡️ Check Expired Conspiracies",
        replace_existing=True,
    )

    scheduler.add_job(
        check_unowned_castles,
        trigger=IntervalTrigger(minutes=10),
        args=[bot],
        id="check_unowned_castles",
        name="🏰 Check Unowned Castles",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("⏰ APScheduler started with %d jobs", len(scheduler.get_jobs()))

    return scheduler


async def check_unowned_castles(bot: Bot) -> None:
    """If 24h passed since first user, give unowned castles a garrison."""
    from bot.models.db import AsyncSessionLocal, User, Castle
    from sqlalchemy import select, func
    from datetime import datetime, timedelta
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.min(User.created_at)))
        first_created = result.scalar()
        if not first_created:
            return
            
        if datetime.utcnow() - first_created > timedelta(hours=24):
            # Check if NPC exists
            npc = await session.get(User, 0)
            if not npc:
                npc = User(user_id=0, username="wildlings", first_name="Дикуни", role="npc", army_size=10000)
                session.add(npc)
                await session.flush()

            castles_res = await session.execute(select(Castle).where(Castle.owner_id == None))
            unowned = castles_res.scalars().all()
            if unowned:
                for c in unowned:
                    c.owner_id = 0
                    c.garrison = 500  # Default NPC garrison
                await session.commit()
                logger.info(f"🏰 {len(unowned)} unowned castles were claimed by the Wildlings!")


async def check_expired_conspiracies(bot: Bot) -> None:
    """Check for and resolve conspiracies that have expired but were missed by the scheduler."""
    from bot.models.db import AsyncSessionLocal, Conspiracy
    from bot.services.conspiracy import resolve_conspiracy, finish_conspiracy
    from sqlalchemy import select, or_, and_
    from datetime import datetime, timedelta
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conspiracy).where(
                or_(
                    and_(Conspiracy.status == "active", Conspiracy.expires_at <= datetime.utcnow()),
                    and_(Conspiracy.status == "battling", Conspiracy.expires_at <= datetime.utcnow() - timedelta(minutes=10))
                )
            )
        )
        expired = result.scalars().all()
        
    for consp in expired:
        if consp.status == "active":
            logger.info(f"Auto-resolving expired conspiracy {consp.conspiracy_id}")
            await resolve_conspiracy(consp.conspiracy_id, bot)
        elif consp.status == "battling":
            logger.info(f"Auto-finishing stuck battling conspiracy {consp.conspiracy_id}")
            await finish_conspiracy(consp.conspiracy_id, bot)


async def broadcast_poll(bot: Bot) -> None:
    """Send secret opinion poll to all users except the king."""
    from bot.models.db import AsyncSessionLocal, User, get_king
    from bot.handlers.poll import PollOpinionCallback
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from sqlalchemy import select
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Хороша", callback_data=PollOpinionCallback(opinion="good").pack()),
            InlineKeyboardButton(text="👎 Погана", callback_data=PollOpinionCallback(opinion="bad").pack()),
            InlineKeyboardButton(text="😐 Нейтральна", callback_data=PollOpinionCallback(opinion="neutral").pack())
        ]
    ])
    
    async with AsyncSessionLocal() as session:
        king = await get_king(session)
        king_id = king.user_id if king else None
        
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            if u.user_id == king_id:
                continue
                
            try:
                await bot.send_message(
                    chat_id=u.user_id,
                    text="👀 <b>Таємне Опитування</b>\n\nЩо ви думаєте про правління поточного Короля?\nВаша відповідь абсолютно таємна і не впливає на ваші дії у Великій Змові.",
                    reply_markup=markup
                )
            except Exception as e:
                logger.error(f"Failed to send poll to {u.user_id}: {e}")


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


def schedule_king_conspiracy_notification(
    conspiracy_id: int, bot: Bot
) -> None:
    """Schedule a random notification to the King about the conspiracy."""
    import random
    from bot.services.conspiracy import notify_king_conspiracy
    
    # Random delay between 1 and 60 minutes
    delay_minutes = random.randint(1, 60)
    run_date = datetime.utcnow() + timedelta(minutes=delay_minutes)
    
    scheduler.add_job(
        notify_king_conspiracy,
        trigger=DateTrigger(run_date=run_date),
        args=[conspiracy_id, bot],
        id=f"notify_king_consp_{conspiracy_id}",
        name=f"👑 Notify King of Conspiracy #{conspiracy_id}",
        replace_existing=True,
    )
    logger.info(f"Scheduled King notification for conspiracy {conspiracy_id} in {delay_minutes} minutes")
