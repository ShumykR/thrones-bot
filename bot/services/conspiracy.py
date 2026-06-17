"""
ThroneChat — Conspiracy Service
Core conspiracy logic: initiation, voting, resolution.
Великі Змови проти Корони.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot

from bot.models.db import (
    AsyncSessionLocal,
    Castle,
    Conspiracy,
    User,
    get_active_conspiracy,
    get_king,
    get_user,
    get_user_castles,
)
from bot.keyboards.inline import conspiracy_keyboard
from bot.texts import messages as msg
from config.config import (
    BATTLE_RAND_MAX,
    BATTLE_RAND_MIN,
    CHAT_ID,
    CONSPIRACY_DURATION_H,
    CONSPIRACY_LOSER_PENALTY,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# 🗡️ Start Conspiracy
# ═══════════════════════════════════════

async def start_conspiracy(
    session: AsyncSession,
    chat_id: int,
    initiator_id: int,
    bot: Bot,
) -> Optional[Conspiracy]:
    """
    Start a new conspiracy against the current King.

    Validates:
    - No active conspiracy already running
    - Initiator is not the King
    - Initiator is not a puppet

    Creates the Conspiracy record, posts a live message to the group chat
    with voting keyboard, and schedules automatic resolution.
    """
    # --- Validation ---
    existing = await get_active_conspiracy(session, chat_id)
    if existing:
        logger.info(
            "Conspiracy rejected: active conspiracy %d already exists",
            existing.conspiracy_id,
        )
        return None

    initiator = await get_user(session, initiator_id)
    if not initiator:
        logger.warning("Conspiracy rejected: initiator %d not registered", initiator_id)
        return None

    if initiator.role == "king":
        logger.info("Conspiracy rejected: initiator %d is the King", initiator_id)
        return None

    if initiator.role == "puppet":
        logger.info("Conspiracy rejected: initiator %d is a puppet", initiator_id)
        return None

    king = await get_king(session)
    if not king:
        logger.info("Conspiracy rejected: no king on the throne")
        return None

    # --- Create Conspiracy ---
    expires_at = datetime.utcnow() + timedelta(hours=CONSPIRACY_DURATION_H)

    # Initiator automatically joins as rebel, committing half their army
    army_commit = max(1, initiator.army_size // 2)
    rebels = {str(initiator_id): army_commit}

    conspiracy = Conspiracy(
        chat_id=chat_id,
        initiator_id=initiator_id,
        status="active",
        rebels=rebels,
        loyalists={},
        expires_at=expires_at,
    )
    session.add(conspiracy)
    await session.flush()  # Get conspiracy_id

    # --- Post live message to group chat ---
    king_name = f"@{king.username}" if king.username else king.first_name
    text = build_conspiracy_text(conspiracy, king_name)

    try:
        sent_msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=conspiracy_keyboard(conspiracy.conspiracy_id),
        )
        conspiracy.message_id = sent_msg.message_id
    except Exception:
        logger.exception("Failed to send conspiracy announcement")

    await session.commit()

    # --- Schedule resolution ---
    from bot.services.scheduler import schedule_conspiracy_resolution
    schedule_conspiracy_resolution(conspiracy.conspiracy_id, expires_at, bot)

    logger.info(
        "Conspiracy %d started by user %d, expires at %s",
        conspiracy.conspiracy_id, initiator_id, expires_at.isoformat(),
    )

    return conspiracy


# ═══════════════════════════════════════
# 🗳️ Join Conspiracy (Vote)
# ═══════════════════════════════════════

async def join_conspiracy(
    session: AsyncSession,
    conspiracy_id: int,
    user_id: int,
    side: str,
    army_to_commit: int,
    bot: Bot,
) -> str:
    """
    Join a conspiracy on a given side: 'rebel', 'loyalist', or 'neutral'.

    - Removes the user from the other side if switching.
    - Adds to chosen side with committed army amount.
    - 'neutral' removes from both sides.
    - Updates the live message with new counts.

    Returns a status string for the callback answer.
    """
    conspiracy = await session.get(Conspiracy, conspiracy_id)
    if not conspiracy or conspiracy.status != "active":
        return "🗡️ Ця змова вже завершена!"

    user = await get_user(session, user_id)
    if not user:
        return "📜 Вас немає у Великій Книзі! Надішліть /start боту."

    # King cannot vote
    if user.role == "king":
        return "👑 Король не може голосувати у змові проти самого себе!"

    uid_str = str(user_id)

    # Work with mutable copies of the JSON fields
    rebels = dict(conspiracy.rebels or {})
    loyalists = dict(conspiracy.loyalists or {})

    # Clamp army commitment
    army_to_commit = max(1, min(army_to_commit, user.army_size))

    if side == "neutral":
        # Remove from both sides
        rebels.pop(uid_str, None)
        loyalists.pop(uid_str, None)
        result_text = "🕊️ Ви обрали нейтралітет."
    elif side == "rebel":
        loyalists.pop(uid_str, None)
        rebels[uid_str] = army_to_commit
        result_text = f"⚔️ Ви приєднались до повстанців! ({army_to_commit} воїнів)"
    elif side == "loyalist":
        rebels.pop(uid_str, None)
        loyalists[uid_str] = army_to_commit
        result_text = f"👑 Ви підтримали Корону! ({army_to_commit} воїнів)"
    else:
        return "❌ Невідома сторона."

    # Update conspiracy record
    conspiracy.rebels = rebels
    conspiracy.loyalists = loyalists
    await session.commit()

    # --- Update live message ---
    king = await get_king(session)
    king_name = "Невідомий"
    if king:
        king_name = f"@{king.username}" if king.username else king.first_name

    text = build_conspiracy_text(conspiracy, king_name)

    try:
        if conspiracy.message_id:
            await bot.edit_message_text(
                chat_id=conspiracy.chat_id,
                message_id=conspiracy.message_id,
                text=text,
                reply_markup=conspiracy_keyboard(conspiracy.conspiracy_id),
            )
    except Exception:
        logger.exception(
            "Failed to update conspiracy %d live message", conspiracy_id
        )

    return result_text


# ═══════════════════════════════════════
# ⚖️ Resolve Conspiracy
# ═══════════════════════════════════════

async def resolve_conspiracy(conspiracy_id: int, bot: Bot) -> None:
    """
    Resolve a conspiracy when the timer expires.

    Calculates:
      rebel_power   = sum(rebels.values())   × random(0.8, 1.2)
      loyalist_power = (king.army_size + sum(loyalists.values())) × random(0.8, 1.2)

    If rebels win:
      - King becomes a lord, loses all castles except one
      - The rebel who committed the most army becomes the new King

    If loyalists/king win:
      - All rebels lose CONSPIRACY_LOSER_PENALTY (50%) of their army (min 1)

    Updates conspiracy status and edits the live message.
    """
    async with AsyncSessionLocal() as session:
        conspiracy = await session.get(Conspiracy, conspiracy_id)
        if not conspiracy or conspiracy.status != "active":
            logger.warning(
                "Conspiracy %s not found or already resolved", conspiracy_id
            )
            return

        king = await get_king(session)
        if not king:
            logger.error("Conspiracy %d: no king found during resolution", conspiracy_id)
            conspiracy.status = "failed"
            await session.commit()
            return

        rebels = conspiracy.rebels or {}
        loyalists = conspiracy.loyalists or {}

        # --- Calculate power ---
        rebel_total = sum(rebels.values()) if rebels else 0
        loyalist_total = (
            king.army_size + sum(loyalists.values())
        ) if loyalists else king.army_size

        rebel_power = rebel_total * random.uniform(BATTLE_RAND_MIN, BATTLE_RAND_MAX)
        loyalist_power = loyalist_total * random.uniform(
            BATTLE_RAND_MIN, BATTLE_RAND_MAX
        )

        king_name = f"@{king.username}" if king.username else king.first_name

        if rebel_power > loyalist_power and rebel_total > 0:
            # ═══ REBELS WIN ═══
            conspiracy.status = "won"

            # Find the rebel with the most army committed
            new_king_uid = max(rebels, key=rebels.get)
            new_king = await get_user(session, int(new_king_uid))

            # Dethrone old king: becomes lord, loses all castles except one
            king.role = "lord"
            king_castles = await get_user_castles(session, king.user_id)
            if len(king_castles) > 1:
                # Keep only the first castle, release the rest
                for castle in king_castles[1:]:
                    castle.owner_id = None

            # Crown new king
            if new_king:
                new_king.role = "king"
                new_king_name = (
                    f"@{new_king.username}" if new_king.username else new_king.first_name
                )
            else:
                new_king_name = "Невідомий Лорд"

            text = msg.CONSPIRACY_WON.format(
                rebel_power=round(rebel_power),
                loyalist_power=round(loyalist_power),
                new_king_name=new_king_name,
            )

            logger.info(
                "Conspiracy %d: REBELS WON — new king is %s",
                conspiracy_id, new_king_uid,
            )
        else:
            # ═══ KING WINS ═══
            conspiracy.status = "failed"

            # Punish rebels: lose CONSPIRACY_LOSER_PENALTY of army
            for uid_str in rebels:
                rebel_user = await get_user(session, int(uid_str))
                if rebel_user:
                    penalty = int(rebel_user.army_size * CONSPIRACY_LOSER_PENALTY)
                    rebel_user.army_size = max(1, rebel_user.army_size - penalty)

            text = msg.CONSPIRACY_FAILED.format(
                king_name=king_name,
                rebel_power=round(rebel_power),
                loyalist_power=round(loyalist_power),
            )

            logger.info(
                "Conspiracy %d: KING WON — rebels punished", conspiracy_id
            )

        await session.commit()

        # --- Edit live message with result ---
        try:
            if conspiracy.message_id:
                await bot.edit_message_text(
                    chat_id=conspiracy.chat_id,
                    message_id=conspiracy.message_id,
                    text=text,
                    reply_markup=None,  # Remove voting buttons
                )
            else:
                await bot.send_message(chat_id=conspiracy.chat_id, text=text)
        except Exception:
            logger.exception("Failed to edit conspiracy result message")
            try:
                await bot.send_message(chat_id=conspiracy.chat_id, text=text)
            except Exception:
                logger.exception("Failed to send fallback conspiracy result message")


# ═══════════════════════════════════════
# 📜 Build Conspiracy Text
# ═══════════════════════════════════════

def build_conspiracy_text(
    conspiracy: Conspiracy, king_name: str = "Невідомий"
) -> str:
    """
    Build the live message text for an active conspiracy,
    showing rebel and loyalist counts.
    """
    rebels = conspiracy.rebels or {}
    loyalists = conspiracy.loyalists or {}

    rebel_count = len(rebels)
    loyalist_count = len(loyalists)

    return msg.CONSPIRACY_STARTED.format(
        king_name=king_name,
        rebel_count=rebel_count,
        loyalist_count=loyalist_count,
    )
