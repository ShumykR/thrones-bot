"""
ThroneChat — King Service
King-specific powers: mute, punish, decree.
"""

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import ChatPermissions
from aiogram.exceptions import TelegramBadRequest

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.db import User, get_user
from bot.texts import messages as msg
from config.config import CHAT_ID, MUTE_DURATION_MINUTES

logger = logging.getLogger(__name__)


async def king_mute(
    bot: Bot,
    session: AsyncSession,
    king_id: int,
    target_id: int,
    duration_minutes: int = MUTE_DURATION_MINUTES,
) -> str:
    """
    King throws a Lord into the dungeon (restrict chat member).
    Returns atmospheric response text.
    """
    king = await get_user(session, king_id)
    if not king or king.role != "king":
        return msg.ERR_NOT_KING

    target = await get_user(session, target_id)
    if not target:
        return "⚔️ Цей Лорд не знайдений у Великій Книзі!"

    try:
        until = datetime.now() + timedelta(minutes=duration_minutes)
        await bot.restrict_chat_member(
            chat_id=CHAT_ID,
            user_id=target_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        target.muted_until = until
        await session.commit()

        target_name = f"@{target.username}" if target.username else target.first_name
        logger.info("King %s muted %s until %s", king_id, target_id, until)
        return msg.KING_MUTE.format(
            target_name=target_name,
            minutes=duration_minutes,
        )

    except TelegramBadRequest as e:
        if "not enough rights" in str(e).lower():
            return msg.KING_MUTE_IMMUNE
        logger.exception("Failed to mute user %s", target_id)
        return "⚠️ Не вдалося виконати наказ Короля. Боги завадили."


async def king_unmute(
    bot: Bot,
    session: AsyncSession,
    king_id: int,
    target_id: int,
) -> str:
    """
    King releases a Lord from the dungeon early.
    """
    king = await get_user(session, king_id)
    if not king or king.role != "king":
        return msg.ERR_NOT_KING

    target = await get_user(session, target_id)
    if not target:
        return "⚔️ Цей Лорд не знайдений у Великій Книзі!"

    try:
        await bot.restrict_chat_member(
            chat_id=CHAT_ID,
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        target.muted_until = None
        await session.commit()

        target_name = f"@{target.username}" if target.username else target.first_name
        logger.info("King %s unmuted %s", king_id, target_id)
        return f"🔓 <b>{target_name}</b> звільнено з темниці милістю Короля!"

    except TelegramBadRequest:
        logger.exception("Failed to unmute user %s", target_id)
        return "⚠️ Не вдалося звільнити цього Лорда."
