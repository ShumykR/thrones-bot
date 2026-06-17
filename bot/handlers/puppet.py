"""
ThroneChat — Puppet Handlers
/rebel, /sabotage, /mercy, /garrison
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from sqlalchemy import select

from bot.models.db import (
    AsyncSessionLocal,
    Castle,
    User,
    get_user,
    get_user_castles,
)
from bot.services.puppet import (
    apply_mercy,
    attempt_rebellion,
    sabotage_master,
    set_garrison,
)
from bot.texts import messages as msg
from config.config import CHAT_ID, REBEL_THRESHOLD

logger = logging.getLogger(__name__)

router = Router(name="puppet")


# ═══════════════════════════════════════
# /rebel — Puppet rebellion
# ═══════════════════════════════════════

@router.message(Command("rebel"))
async def rebel_handler(message: Message) -> None:
    """
    Only puppets with IP >= 100 can attempt rebellion.
    Compares puppet army vs master's garrison.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(msg.ERR_NOT_REGISTERED)
            return

        if user.role != "puppet":
            await message.answer("⛓️ Лише маріонетки можуть піднімати повстання!")
            return

        if user.independence_points < REBEL_THRESHOLD:
            await message.answer(
                f"🔒 Недостатньо балів незалежності! "
                f"({user.independence_points}/{REBEL_THRESHOLD})"
            )
            return

        success, text = await attempt_rebellion(
            session, message.from_user.id, message.bot, CHAT_ID,
        )
        # Response was already sent to the group chat by attempt_rebellion;
        # reply privately to the puppet as confirmation.
        try:
            if success:
                await message.answer("🗡️ Ви вільні! Ви знову Лорд Вестеросу!")
            else:
                await message.answer("⛓️ Повстання провалилось... Ваші БН зменшено.")
        except Exception:
            logger.exception("Failed to reply to /rebel command")


# ═══════════════════════════════════════
# /sabotage — Puppet sabotages master
# ═══════════════════════════════════════

@router.message(Command("sabotage"))
async def sabotage_handler(message: Message) -> None:
    """
    Puppet conducts sabotage on master's castles (once per 24h).
    Reduces master's army_per_hour by 30% for 6 hours.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(msg.ERR_NOT_REGISTERED)
            return

        if user.role != "puppet":
            await message.answer("⛓️ Лише маріонетки можуть проводити диверсії!")
            return

        text = await sabotage_master(
            session, message.from_user.id, message.bot, CHAT_ID,
        )

        try:
            await message.answer(text)
        except Exception:
            logger.exception("Failed to reply to /sabotage command")


# ═══════════════════════════════════════
# /mercy @puppet — Master shows mercy
# ═══════════════════════════════════════

@router.message(Command("mercy"))
async def mercy_handler(message: Message, command: CommandObject) -> None:
    """
    Master shows mercy to a puppet, reducing their IP by 20.
    Usage: /mercy @puppet_username
    """
    async with AsyncSessionLocal() as session:
        master = await get_user(session, message.from_user.id)
        if not master:
            await message.answer(msg.ERR_NOT_REGISTERED)
            return

        # Parse target puppet from mentions or reply
        puppet_user_id = await _resolve_puppet_target(message, command)
        if not puppet_user_id:
            await message.answer(
                "⚠️ Вкажіть маріонетку: /mercy @username або відповідь на повідомлення."
            )
            return

        text = await apply_mercy(session, message.from_user.id, puppet_user_id)

        try:
            await message.answer(text)
        except Exception:
            logger.exception("Failed to reply to /mercy command")


# ═══════════════════════════════════════
# /garrison N [@castle] — Set garrison
# ═══════════════════════════════════════

@router.message(Command("garrison"))
async def garrison_handler(message: Message, command: CommandObject) -> None:
    """
    Set garrison for a castle.
    Usage: /garrison 50 Вінтерфелл
           /garrison 50  (uses first owned castle)
    """
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(msg.ERR_NOT_REGISTERED)
            return

        if not command.args:
            await message.answer(
                "⚠️ Використання: /garrison <кількість> [назва замку]\n"
                "Приклад: /garrison 50 Вінтерфелл"
            )
            return

        # Parse arguments
        parts = command.args.split(maxsplit=1)
        try:
            amount = int(parts[0])
        except ValueError:
            await message.answer("⚠️ Кількість має бути числом! Приклад: /garrison 50")
            return

        if amount < 0:
            await message.answer("⚠️ Кількість не може бути від'ємною!")
            return

        castle_name = parts[1].strip() if len(parts) > 1 else None

        # Find the castle
        if castle_name:
            # Search by name
            result = await session.execute(
                select(Castle).where(
                    Castle.owner_id == user.user_id,
                    Castle.name == castle_name,
                )
            )
            castle = result.scalar_one_or_none()
            if not castle:
                await message.answer(
                    f"🏰 Замок «{castle_name}» не знайдено серед ваших замків!"
                )
                return
        else:
            # Use first owned castle
            castles = await get_user_castles(session, user.user_id)
            if not castles:
                await message.answer("🏰 У вас немає замків для розміщення гарнізону!")
                return
            castle = castles[0]

        text = await set_garrison(session, user.user_id, castle.castle_id, amount)

        try:
            await message.answer(text)
        except Exception:
            logger.exception("Failed to reply to /garrison command")


# ═══════════════════════════════════════
# 🔧 Helpers
# ═══════════════════════════════════════

async def _resolve_puppet_target(
    message: Message,
    command: CommandObject,
) -> int | None:
    """
    Resolve the target puppet user_id from:
    1. Reply to a message
    2. @username in command args
    3. User mention entity in the message
    Returns user_id or None.
    """
    # 1. Reply
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    # 2. Mention entities
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention" and command.args:
                # Extract @username
                username = command.args.strip().lstrip("@")
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(User).where(User.username == username)
                    )
                    target = result.scalar_one_or_none()
                    if target:
                        return target.user_id
                return None

            if entity.type == "text_mention" and entity.user:
                return entity.user.id

    # 3. Plain text username arg
    if command.args:
        username = command.args.strip().lstrip("@")
        if username:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.username == username)
                )
                target = result.scalar_one_or_none()
                if target:
                    return target.user_id

    return None
