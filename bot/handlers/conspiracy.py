"""
ThroneChat — Conspiracy Handlers
Deep link initiation and inline voting callbacks.
"""

import logging

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from bot.keyboards.inline import ConspiracyVoteCallback
from bot.models.db import (
    AsyncSessionLocal,
    get_user,
)
from bot.services.conspiracy import join_conspiracy, start_conspiracy
from config.config import CHAT_ID

logger = logging.getLogger(__name__)

router = Router(name="conspiracy")


# ═══════════════════════════════════════
# 🗳️ Conspiracy Vote Callback
# ═══════════════════════════════════════

@router.callback_query(ConspiracyVoteCallback.filter())
async def conspiracy_vote_handler(
    query: CallbackQuery,
    callback_data: ConspiracyVoteCallback,
    bot: Bot,
) -> None:
    """
    Handle conspiracy voting buttons: rebel / loyalist / neutral.

    Uses half of the voter's army as the committed amount.
    Always calls query.answer() to dismiss the loading spinner.
    """
    await query.answer()

    user_id = query.from_user.id
    side = callback_data.action
    conspiracy_id = callback_data.conspiracy_id

    async with AsyncSessionLocal() as session:
        # Get user to calculate army commitment
        user = await get_user(session, user_id)
        if not user:
            try:
                await query.message.answer(
                    "📜 Вас немає у Великій Книзі! Надішліть /start боту в ПП."
                )
            except Exception:
                logger.exception("Failed to send unregistered message")
            return

        # Commit half of user's army
        army_to_commit = max(1, user.army_size // 2)

        result_text = await join_conspiracy(
            session=session,
            conspiracy_id=conspiracy_id,
            user_id=user_id,
            side=side,
            army_to_commit=army_to_commit,
            bot=bot,
        )

    # Notify the voter with a popup
    try:
        await query.answer(result_text, show_alert=True)
    except Exception:
        # answer() may have already been called above; ignore duplicates
        logger.debug("Duplicate query.answer for conspiracy vote")


# ═══════════════════════════════════════
# 🗡️ Deep Link Handler (called from common.py)
# ═══════════════════════════════════════

async def handle_conspiracy_deeplink(
    user_id: int,
    chat_id: int,
    bot: Bot,
) -> str:
    """
    Called from common.py when a /start conspiracy_{chat_id} deep link is received.

    Returns a status message to send back to the user in private.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            return "📜 Ви ще не записані у Великій Книзі. Надішліть /start боту спочатку."

        if user.role == "king":
            return "👑 Ви — Король! Ви не можете змовлятися проти самого себе."

        if user.role == "puppet":
            return "⛓️ Маріонетка не може починати змову. Спершу здобудьте свободу!"

        conspiracy = await start_conspiracy(
            session=session,
            chat_id=chat_id,
            initiator_id=user_id,
            bot=bot,
        )

        if conspiracy:
            return (
                "🗡️ Велика Змова розпочата!\n"
                "Повідомлення з голосуванням надіслано до чату.\n"
                "⏳ Рішення буде прийнято через 4 години."
            )
        else:
            return (
                "⚠️ Не вдалось розпочати змову.\n"
                "Можливо, вже є активна змова, або трон порожній."
            )
