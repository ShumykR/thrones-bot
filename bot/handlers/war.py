"""
ThroneChat — War Handlers
/attack command and battle-related callback handlers.
"""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from sqlalchemy import select

from bot.models.db import (
    AsyncSessionLocal,
    Battle,
    Castle,
    User,
    count_user_castles,
    get_active_battle_for_user,
    get_user,
    get_user_castles,
)
from bot.services.scheduler import schedule_battle_resolution
from bot.texts import messages as msg
from config.config import CHAT_ID

logger = logging.getLogger(__name__)

router = Router(name="war")


# ═══════════════════════════════════════
# /attack @username кількість — Start a battle
# ═══════════════════════════════════════

@router.message(Command("attack"))
async def attack_handler(message: Message, bot: Bot) -> None:
    """
    Handle /attack @username amount
    Validates all conditions, creates a pending battle,
    posts announcement to chat, schedules resolution.
    """
    async with AsyncSessionLocal() as session:
        # --- Parse arguments ---
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.reply(
                "⚔️ Формат: <code>/attack @username кількість</code>\n"
                "Наприклад: <code>/attack @rival 200</code>"
            )
            return

        target_identifier = args[1]
        try:
            army_amount = int(args[2])
        except ValueError:
            await message.reply("⚔️ Кількість воїнів має бути числом!")
            return

        # --- Get attacker ---
        attacker = await get_user(session, message.from_user.id)
        if not attacker:
            await message.reply(msg.ERR_NOT_REGISTERED)
            return

        # --- Minimum army check ---
        if army_amount < 100:
            await message.reply(msg.ERR_ATTACK_NOT_ENOUGH_ARMY)
            return

        if army_amount > attacker.army_size:
            await message.reply(
                f"⚔️ У вас лише <b>{attacker.army_size}</b> воїнів, "
                f"а ви хочете відправити <b>{army_amount}</b>!"
            )
            return

        # --- Check active battle ---
        active_battle = await get_active_battle_for_user(session, attacker.user_id)
        if active_battle:
            await message.reply(msg.ERR_ATTACK_ACTIVE_BATTLE)
            return

        # --- Find defender by @username or user_id ---
        target_username = target_identifier.lstrip("@")
        result = await session.execute(
            select(User).where(User.username == target_username)
        )
        defender = result.scalar_one_or_none()

        if not defender:
            await message.reply(
                f"⚔️ Лорд <b>@{target_username}</b> не знайдений у Великій Книзі!"
            )
            return

        # --- Self-attack check ---
        if defender.user_id == attacker.user_id:
            await message.reply(msg.ERR_ATTACK_SELF)
            return

        # --- Puppet cannot attack master ---
        if attacker.role == "puppet" and attacker.master_id == defender.user_id:
            await message.reply(msg.ERR_ATTACK_MASTER)
            return

        # --- Alliance check ---
        if (
            attacker.alliance_id
            and defender.alliance_id
            and attacker.alliance_id == defender.alliance_id
        ):
            await message.reply(msg.ERR_ATTACK_ALLY)
            return

        # --- Defender must have castles ---
        defender_castles = await get_user_castles(session, defender.user_id)
        if not defender_castles:
            await message.reply(msg.ERR_ATTACK_NO_CASTLE)
            return

        # Pick the first castle as target (simplification — later WebApp will allow picking)
        target_castle = defender_castles[0]

        # --- Deduct army from attacker (they're committed to the march) ---
        attacker.army_size -= army_amount

        # --- Create battle record ---
        battle = Battle(
            attacker_id=attacker.user_id,
            defender_id=defender.user_id,
            castle_id=target_castle.castle_id,
            attacker_army=army_amount,
            started_at=datetime.utcnow(),
        )
        session.add(battle)
        await session.flush()  # Get battle_id

        # --- Post announcement to group chat ---
        atk_name = f"@{attacker.username}" if attacker.username else attacker.first_name
        def_name = f"@{defender.username}" if defender.username else defender.first_name

        announcement_text = msg.BATTLE_ANNOUNCED.format(
            attacker_name=atk_name,
            defender_name=def_name,
            army_sent=army_amount,
            castle_name=target_castle.name,
        )

        try:
            sent_msg = await bot.send_message(
                chat_id=CHAT_ID,
                text=announcement_text,
            )
            battle.message_id = sent_msg.message_id
        except Exception:
            logger.exception("Failed to send battle announcement")

        await session.commit()

        # --- Schedule battle resolution ---
        schedule_battle_resolution(battle.battle_id, bot)

        logger.info(
            "Battle %d started: %s (%d troops) → %s (castle: %s)",
            battle.battle_id, atk_name, army_amount,
            def_name, target_castle.name,
        )

        # Reply to the attacker (confirmation)
        await message.reply(
            f"⚔️ Ваша армія ({army_amount} воїнів) вирушила на штурм "
            f"замку <b>{target_castle.name}</b>!\n"
            f"⏳ Результат буде через 5 хвилин."
        )


# ═══════════════════════════════════════
# 💰 Event Treasure Callback
# ═══════════════════════════════════════

@router.callback_query(lambda c: c.data == "event_treasure")
async def event_treasure_handler(query: CallbackQuery, bot: Bot) -> None:
    """Handle the first-click treasure event button."""
    from bot.services.economy import claim_treasure

    result_text = await claim_treasure(query.from_user.id, bot)
    await query.answer(result_text, show_alert=True)

    # Remove the button after first claim
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception("Failed to remove treasure button")
