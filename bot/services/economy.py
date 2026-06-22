"""
ThroneChat — Economy Service
Hourly income tick, random events.
"""

import logging
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models.db import (
    AsyncSessionLocal,
    Castle,
    User,
    count_user_castles,
    get_army_cap,
    get_user,
    get_user_castles,
)
from bot.texts import messages as msg
from config.config import (
    BASE_INCOME,
    CASTLE_INCOME,
    CHAT_ID,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# 💰 Hourly Economy Tick
# ═══════════════════════════════════════

async def economy_tick(bot: Bot) -> None:
    """
    Called every hour by APScheduler.
    - Each user with castles: +castle.army_per_hour per castle
    - Users with 0 castles: +BASE_INCOME (2 troops/hr)
    - Army capped at BASE_CAP + (castle_count × CASTLE_CAP)
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        # Find the king to give taxes to
        king = None
        for user in users:
            if user.role == "king":
                king = user
                break

        for user in users:
            castles = await get_user_castles(session, user.user_id)

            if not castles:
                income = BASE_INCOME
            else:
                income = sum(c.army_per_hour for c in castles)

            # King's Tribute: based on dynamic king_tribute_rate
            if user.role != "king" and king and user.king_tribute_rate > 0:
                king_tax = int(income * user.king_tribute_rate)
                income -= king_tax
                king_cap = await get_army_cap(session, king.user_id)
                king.army_size = min(king.army_size + king_tax, king_cap)
            # Apply income with army cap
            army_cap = await get_army_cap(session, user.user_id)
            user.army_size = min(user.army_size + income, army_cap)

        await session.commit()
        logger.info("Economy tick: processed %d users", len(users))


# ═══════════════════════════════════════
# 📅 Daily Tick
# ═══════════════════════════════════════

async def daily_tick(bot: Bot) -> None:
    """
    Called every 24 hours by APScheduler.
    - Trigger a random daily event
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
        )
        users = result.scalars().all()
        
        # Calculate King's authority based on opinions
        king = next((u for u in users if u.role == "king"), None)
        if king:
            loyalists = sum(1 for u in users if u.king_opinion == "good" and u.role != "king")
            rebels = sum(1 for u in users if u.king_opinion == "bad" and u.role != "king")
            
            auth_change = 10 + (loyalists * 5) - (rebels * 5)
            
            king.authority = max(0, min(100, king.authority + auth_change))

        await session.commit()

    # Trigger random event
    await trigger_daily_event(bot)



# ═══════════════════════════════════════
# 📯 Random Daily Events
# ═══════════════════════════════════════

DAILY_EVENTS = [
    {
        "text": "❄️ Настала зима! Приріст військ у всіх знижено на 20% на наступні 12 годин.",
        "effect": "winter_20",
        "duration_hours": 12,
    },
    {
        "text": "💰 Купці з Ессосу прибули! +300 воїнів першому, хто натисне кнопку!",
        "effect": "first_click_bonus",
        "bonus": 300,
    },
    {
        "text": "⚔️ Банди мародерів гуляють по землях! Лорди без замків втрачають 50 воїнів.",
        "effect": "marauders",
        "penalty": 50,
    },
    {
        "text": "🐉 Дракон пролетів над Вестеросом! Найсильніший Лорд отримує +200 воїнів.",
        "effect": "dragon_blessing",
        "bonus": 200,
    },
    {
        "text": "🍷 Бенкет у Королівській Гавані! Усі гравці отримують +100 воїнів.",
        "effect": "feast",
        "bonus": 100,
    },
    {
        "text": "🌑 Тінь пронеслась над землями... Армії всіх Лордів зменшуються на 10%.",
        "effect": "shadow_plague",
        "penalty_pct": 0.10,
    },
    {
        "text": "🏰 Каменярі з Вільних Міст пропонують послуги! Усі замки отримують +2 до приросту на 12 годин.",
        "effect": "masons",
        "bonus_per_hour": 2,
        "duration_hours": 12,
    },
]


async def trigger_daily_event(bot: Bot) -> None:
    """Pick and apply a random daily event."""
    event = random.choice(DAILY_EVENTS)

    async with AsyncSessionLocal() as session:
        keyboard = None

        if event["effect"] == "first_click_bonus":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="💰 Забрати скарб!",
                    callback_data="event_treasure",
                )
            ]])

        elif event["effect"] == "marauders":
            # Apply penalty to castleless lords
            result = await session.execute(select(User))
            for user in result.scalars().all():
                castle_count = await count_user_castles(session, user.user_id)
                if castle_count == 0:
                    user.army_size = max(1, user.army_size - event["penalty"])
            await session.commit()

        elif event["effect"] == "dragon_blessing":
            # Give bonus to strongest lord
            result = await session.execute(
                select(User).order_by(User.army_size.desc()).limit(1)
            )
            strongest = result.scalar_one_or_none()
            if strongest:
                cap = await get_army_cap(session, strongest.user_id)
                strongest.army_size = min(strongest.army_size + event["bonus"], cap)
                await session.commit()

        elif event["effect"] == "feast":
            # Give bonus to everyone
            result = await session.execute(select(User))
            for user in result.scalars().all():
                cap = await get_army_cap(session, user.user_id)
                user.army_size = min(user.army_size + event["bonus"], cap)
            await session.commit()

        elif event["effect"] == "shadow_plague":
            # Reduce everyone's army by 10%
            result = await session.execute(select(User))
            for user in result.scalars().all():
                loss = int(user.army_size * event["penalty_pct"])
                user.army_size = max(1, user.army_size - loss)
            await session.commit()

        elif event["effect"] == "winter_20":
            # Reduce all castle production by 20% (temporary)
            result = await session.execute(select(Castle))
            for castle in result.scalars().all():
                castle.army_per_hour = max(1, int(castle.army_per_hour * 0.80))
            await session.commit()
            # TODO: Schedule restoration after duration_hours

        elif event["effect"] == "masons":
            # Boost all castle production by +2 (temporary)
            result = await session.execute(select(Castle))
            for castle in result.scalars().all():
                castle.army_per_hour += event["bonus_per_hour"]
            await session.commit()
            # TODO: Schedule restoration after duration_hours

        try:
            await bot.send_message(
                CHAT_ID,
                msg.EVENT_HEADER + event["text"],
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception("Failed to send daily event message")

    logger.info("Daily event triggered: %s", event["effect"])


# ═══════════════════════════════════════
# 💰 First-Click Treasure Handler
# ═══════════════════════════════════════

async def claim_treasure(user_id: int, bot: Bot) -> str:
    """
    Award +300 troops to the first clicker.
    Called from event callback handler.
    Returns response text for the callback answer.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            return "Ви не зареєстровані!"

        cap = await get_army_cap(session, user.user_id)
        bonus = 300
        user.army_size = min(user.army_size + bonus, cap)
        await session.commit()

        user_name = f"@{user.username}" if user.username else user.first_name
        try:
            await bot.send_message(
                CHAT_ID,
                f"💰 <b>{user_name}</b> першим забрав скарб купців! (+{bonus} воїнів)",
            )
        except Exception:
            logger.exception("Failed to send treasure claim message")

        return f"💰 +{bonus} воїнів!"
