"""
ThroneChat — Puppet Service
Rebellion, sabotage, mercy, garrison management.
Handles the lifecycle of puppet-master relationships.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot

from bot.models.db import (
    AsyncSessionLocal,
    Castle,
    User,
    get_user,
    get_user_castles,
)
from bot.texts import messages as msg
from config.config import (
    CHAT_ID,
    GARRISON_FREEZES_IP,
    MERCY_IP_REDUCTION,
    REBEL_THRESHOLD,
    SABOTAGE_IP_GAIN,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# 🗡️ Rebellion
# ═══════════════════════════════════════

async def attempt_rebellion(
    session: AsyncSession,
    puppet_id: int,
    bot: Bot,
    chat_id: int,
) -> tuple[bool, str]:
    """
    Puppet attempts to break free from master.
    Requires IP >= REBEL_THRESHOLD (100).
    Compares puppet army_size vs total garrison of master's castles.
    If puppet wins: role → 'lord', master_id → None, IP → 0.
    If fails: IP -= 30 (min 0).
    Returns (success, message_text).
    """
    puppet = await get_user(session, puppet_id)
    if not puppet or puppet.role != "puppet":
        return False, "⛓️ Ви не є маріонеткою. Команда /rebel лише для маріонеток."

    if puppet.independence_points < REBEL_THRESHOLD:
        return False, (
            f"🔒 Недостатньо балів незалежності! "
            f"({puppet.independence_points}/{REBEL_THRESHOLD})"
        )

    # Get total garrison from master's castles
    garrison_total = await get_garrison_size(session, puppet_id)
    puppet_name = f"@{puppet.username}" if puppet.username else puppet.first_name

    if puppet.army_size > garrison_total:
        # === REBELLION SUCCEEDS ===
        puppet.role = "lord"
        puppet.master_id = None
        puppet.independence_points = 0
        await session.commit()

        text = msg.REBEL_SUCCESS.format(puppet_name=puppet_name)

        try:
            await bot.send_message(chat_id, text)
        except Exception:
            logger.exception("Failed to send rebellion success message")

        logger.info(
            "Rebellion SUCCESS: puppet %d (army=%d) > garrison=%d",
            puppet_id, puppet.army_size, garrison_total,
        )
        return True, text

    else:
        # === REBELLION FAILS ===
        puppet.independence_points = max(0, puppet.independence_points - 30)
        await session.commit()

        text = msg.REBEL_FAILED.format(puppet_name=puppet_name)

        try:
            await bot.send_message(chat_id, text)
        except Exception:
            logger.exception("Failed to send rebellion failure message")

        logger.info(
            "Rebellion FAILED: puppet %d (army=%d) <= garrison=%d",
            puppet_id, puppet.army_size, garrison_total,
        )
        return False, text


# ═══════════════════════════════════════
# 🔥 Sabotage
# ═══════════════════════════════════════

async def sabotage_master(
    session: AsyncSession,
    puppet_id: int,
    bot: Bot,
    chat_id: int,
) -> str:
    """
    Puppet sabotages master's castles: reduce army_per_hour by 30% for 6 hours.
    Cooldown: once per 24 hours. Puppet gets +SABOTAGE_IP_GAIN IP.
    """
    puppet = await get_user(session, puppet_id)
    if not puppet or puppet.role != "puppet":
        return "⛓️ Лише маріонетки можуть проводити диверсії!"

    if not puppet.master_id:
        return "⚠️ У вас немає Власника для диверсії."

    # Check 24h cooldown
    now = datetime.utcnow()
    if puppet.last_sabotage:
        elapsed = now - puppet.last_sabotage
        if elapsed < timedelta(hours=24):
            remaining = timedelta(hours=24) - elapsed
            hours_left = int(remaining.total_seconds() // 3600)
            mins_left = int((remaining.total_seconds() % 3600) // 60)
            return (
                f"⏳ Диверсія ще на перезарядці! "
                f"Спробуйте через {hours_left}г {mins_left}хв."
            )

    master_id = puppet.master_id
    master_castles = await get_user_castles(session, master_id)

    if not master_castles:
        return "🏰 У вашого Власника немає замків для диверсії."

    # Reduce army_per_hour by 30% (min 1)
    for castle in master_castles:
        reduced = max(1, int(castle.army_per_hour * 0.70))
        castle.army_per_hour = reduced

    # Grant IP, update cooldown
    puppet.independence_points = min(100, puppet.independence_points + SABOTAGE_IP_GAIN)
    puppet.last_sabotage = now
    await session.commit()

    # Schedule restoration after 6 hours
    _schedule_sabotage_restore(master_id)

    puppet_name = f"@{puppet.username}" if puppet.username else puppet.first_name
    text = msg.SABOTAGE_SUCCESS.format(puppet_name=puppet_name)

    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("Failed to send sabotage message to chat")

    logger.info(
        "Sabotage: puppet %d sabotaged master %d (%d castles affected, +%d IP)",
        puppet_id, master_id, len(master_castles), SABOTAGE_IP_GAIN,
    )
    return text


def _schedule_sabotage_restore(master_user_id: int) -> None:
    """Schedule a one-off job to restore master's castles after 6 hours."""
    from bot.services.scheduler import scheduler
    from apscheduler.triggers.date import DateTrigger

    run_date = datetime.utcnow() + timedelta(hours=6)

    scheduler.add_job(
        restore_sabotage,
        trigger=DateTrigger(run_date=run_date),
        args=[master_user_id],
        id=f"sabotage_restore_{master_user_id}",
        name=f"🔧 Restore sabotage for master {master_user_id}",
        replace_existing=True,
    )
    logger.info(
        "Scheduled sabotage restore for master %d at %s",
        master_user_id, run_date.isoformat(),
    )


async def restore_sabotage(master_user_id: int) -> None:
    """
    Restore all master's castles army_per_hour to default (10).
    Called by scheduler after 6h sabotage duration.
    """
    async with AsyncSessionLocal() as session:
        castles = await get_user_castles(session, master_user_id)
        for castle in castles:
            castle.army_per_hour = 10
        await session.commit()

    logger.info(
        "Sabotage restored: master %d — %d castles reset to 10 army/hr",
        master_user_id, len(castles),
    )


# ═══════════════════════════════════════
# 🕊️ Mercy
# ═══════════════════════════════════════

async def apply_mercy(
    session: AsyncSession,
    master_id: int,
    puppet_id: int,
) -> str:
    """
    Master shows mercy to puppet: reduce puppet IP by MERCY_IP_REDUCTION (min 0).
    Master must own the puppet.
    """
    master = await get_user(session, master_id)
    if not master:
        return "⚠️ Ви не зареєстровані."

    puppet = await get_user(session, puppet_id)
    if not puppet:
        return "⚠️ Цього гравця не знайдено."

    if puppet.role != "puppet" or puppet.master_id != master_id:
        return "⛓️ Цей гравець не є вашою маріонеткою!"

    puppet.independence_points = max(0, puppet.independence_points - MERCY_IP_REDUCTION)
    await session.commit()

    master_name = f"@{master.username}" if master.username else master.first_name
    puppet_name = f"@{puppet.username}" if puppet.username else puppet.first_name

    text = msg.MERCY_APPLIED.format(
        master_name=master_name,
        puppet_name=puppet_name,
    )

    logger.info(
        "Mercy applied: master %d → puppet %d (IP now %d)",
        master_id, puppet_id, puppet.independence_points,
    )
    return text


# ═══════════════════════════════════════
# 🏰 Garrison
# ═══════════════════════════════════════

async def set_garrison(
    session: AsyncSession,
    owner_id: int,
    castle_id: int,
    amount: int,
) -> str:
    """
    Set garrison for a castle. Deducts soldiers from owner's army.
    Owner must own the castle. Army never goes below 1.
    """
    owner = await get_user(session, owner_id)
    if not owner:
        return "⚠️ Ви не зареєстровані."

    castle = await session.get(Castle, castle_id)
    if not castle:
        return "🏰 Замок не знайдено."

    if castle.owner_id != owner_id:
        return "🏰 Цей замок не належить вам!"

    if amount < 0:
        return "⚠️ Кількість воїнів не може бути від'ємною."

    # Calculate the difference: how many troops to add/remove from garrison
    current_garrison = castle.garrison
    diff = amount - current_garrison  # positive = adding troops, negative = returning

    if diff > 0:
        # Adding troops to garrison — check army
        available = owner.army_size - 1  # keep at least 1
        if diff > available:
            return (
                f"⚔️ Недостатньо воїнів! "
                f"Доступно: {available}, потрібно: {diff}."
            )
        owner.army_size -= diff
    elif diff < 0:
        # Returning troops from garrison to army
        owner.army_size += abs(diff)

    castle.garrison = amount
    await session.commit()

    text = msg.GARRISON_SET.format(
        castle_name=castle.name,
        amount=amount,
    )

    logger.info(
        "Garrison set: owner %d, castle '%s' (#%d), garrison=%d (diff=%+d)",
        owner_id, castle.name, castle_id, amount, diff,
    )
    return text


async def get_garrison_size(
    session: AsyncSession,
    puppet_user_id: int,
) -> int:
    """
    Sum garrison across all castles owned by the puppet's master.
    Returns 0 if puppet has no master or master has no castles.
    """
    puppet = await get_user(session, puppet_user_id)
    if not puppet or not puppet.master_id:
        return 0

    result = await session.execute(
        select(func.coalesce(func.sum(Castle.garrison), 0)).where(
            Castle.owner_id == puppet.master_id
        )
    )
    return result.scalar() or 0
