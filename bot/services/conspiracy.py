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
from config.config import CONSPIRACY_DURATION_MINUTES

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# 🗡️ Start Conspiracy
# ═══════════════════════════════════════

async def start_conspiracy(
    session: AsyncSession,
    chat_id: int,
    initiator_id: int,
    bot: Bot,
    army_commit: int = 0
) -> Optional[Conspiracy]:
    """
    Start a new conspiracy against the current King.
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

    king = await get_king(session)
    if not king:
        logger.info("Conspiracy rejected: no king on the throne")
        return None

    # --- Create Conspiracy ---
    expires_at = datetime.utcnow() + timedelta(minutes=CONSPIRACY_DURATION_MINUTES)

    # Initiator automatically joins as rebel
    army_commit = max(1, min(army_commit, initiator.army_size))
    initiator.army_size -= army_commit
    
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

    # --- Post message to all users in PM ---
    king_name = f"@{king.username}" if king.username else king.first_name
    text = build_conspiracy_text(conspiracy, king_name)

    users = (await session.execute(select(User))).scalars().all()
    for u in users:
        if u.user_id == initiator_id:
            continue
        try:
            await bot.send_message(
                chat_id=u.user_id,
                text=text,
                reply_markup=conspiracy_keyboard(conspiracy.conspiracy_id),
            )
        except Exception:
            pass

    await session.commit()

    # --- Schedule resolution ---
    from bot.services.scheduler import schedule_conspiracy_resolution, schedule_king_conspiracy_notification
    schedule_conspiracy_resolution(conspiracy.conspiracy_id, expires_at, bot)
    schedule_king_conspiracy_notification(conspiracy.conspiracy_id, bot)

    logger.info(
        "Conspiracy %d started by user %d, expires at %s",
        conspiracy.conspiracy_id, initiator_id, expires_at.isoformat(),
    )

    return conspiracy


async def notify_king_conspiracy(conspiracy_id: int, bot: Bot) -> None:
    """Notify the king about the active conspiracy in a delayed PM."""
    async with AsyncSessionLocal() as session:
        conspiracy = await session.get(Conspiracy, conspiracy_id)
        if not conspiracy or conspiracy.status != "active":
            return
            
        king = await get_king(session)
        if king:
            try:
                await bot.send_message(
                    chat_id=king.user_id,
                    text="👑 <b>ТРИВОГА, ВАША МИЛОСТЕ!</b>\n\nНаші шпигуни доносять про змову проти вас! Збирайте лоялістів, інакше ви втратите Трон!"
                )
            except Exception as e:
                logger.error(f"Failed to notify king about conspiracy: {e}")


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
    Join a conspiracy on a given side.
    Subtracts 50% of user's army upon joining. Refunds if changing side.
    """
    conspiracy = await session.get(Conspiracy, conspiracy_id)
    if not conspiracy or conspiracy.status != "active":
        return "🗡️ Ця змова вже завершена!"

    user = await get_user(session, user_id)
    if not user:
        return "📜 Вас немає у Великій Книзі! Надішліть /start боту."

    if user.role == "king":
        return "👑 Король не може голосувати у змові проти самого себе!"

    if user_id == conspiracy.initiator_id:
        return "❌ Ініціатор не може змінити свій вибір."

    uid_str = str(user_id)

    rebels = dict(conspiracy.rebels or {})
    loyalists = dict(conspiracy.loyalists or {})

    # Refund previous commit
    old_commit = 0
    if uid_str in rebels:
        old_commit = rebels.pop(uid_str)
    elif uid_str in loyalists:
        old_commit = loyalists.pop(uid_str)
        
    user.army_size += old_commit

    if side == "neutral":
        result_text = "🕊️ Ви обрали нейтралітет."
    from config.config import CONSPIRACY_REBEL_DEFAULT_PCT
    if side == "rebel":
        army_to_commit = max(1, int(user.army_size * CONSPIRACY_REBEL_DEFAULT_PCT))
        user.army_size -= army_to_commit
        rebels[uid_str] = army_to_commit
        result_text = f"⚔️ Ви приєдналися до Змови! ({army_to_commit} воїнів)"
    elif side == "loyalist":
        army_to_commit = max(1, int(user.army_size * CONSPIRACY_REBEL_DEFAULT_PCT))
        user.army_size -= army_to_commit
        loyalists[uid_str] = army_to_commit
        result_text = f"👑 Ви підтримали Корону! ({army_to_commit} воїнів)"
    else:
        user.army_size -= old_commit
        return "❌ Невідома сторона."

    conspiracy.rebels = rebels
    conspiracy.loyalists = loyalists
    await session.commit()

    return result_text


# ═══════════════════════════════════════
# ⚖️ Resolve Conspiracy
# ═══════════════════════════════════════

async def run_conspiracy_battle(conspiracy_id: int, bot: Bot, chat_id: int, msg_id: int, rebel_total: int, loyalist_total: int, king_name: str, simulation: dict) -> None:
    import asyncio
    
    def make_progress_bar(percent: int, length: int = 15) -> str:
        filled = int((percent / 100) * length)
        return "█" * filled + "░" * (length - filled)

    history = simulation["history"]
    for i, state in enumerate(history, 1):
        await asyncio.sleep(60)
        
        total_alive = state["atk_alive"] + state["def_alive"]
        rebel_chance = int((state["atk_alive"] / total_alive) * 100) if total_alive > 0 else 50
        
        progress = make_progress_bar(rebel_chance)
        
        text = (
            f"🏰 <b>БІЙ ЗА ЗАЛІЗНИЙ ТРОН ТРИВАЄ! (Хвилина {i}/5)</b>\n\n"
            f"Король: {king_name}\n\n"
            f"⚔️ <b>Повстанці:</b>\n"
            f"В строю: {state['atk_alive']} воїнів\n"
            f"Втрати: {state['atk_losses']} воїнів\n\n"
            f"👑 <b>Корона:</b>\n"
            f"В строю: {state['def_alive']} воїнів\n"
            f"Втрати: {state['def_losses']} воїнів\n\n"
            f"📊 <b>Перевага:</b>\n"
            f"Повстанці <code>[{progress}]</code> Корона\n"
            f"({rebel_chance}% / {100 - rebel_chance}%)\n\n"
            f"<i>Очікуйте завершення бою...</i>"
        )
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="HTML")
        except Exception:
            pass

    await finish_conspiracy(conspiracy_id, bot, simulation)


async def finish_conspiracy(conspiracy_id: int, bot: Bot, sim_result: dict = None) -> None:
    async with AsyncSessionLocal() as session:
        conspiracy = await session.get(Conspiracy, conspiracy_id)
        if not conspiracy or conspiracy.status != "battling":
            return

        king = await get_king(session)
        if not king:
            conspiracy.status = "failed"
            await session.commit()
            return

        rebels = conspiracy.rebels or {}
        loyalists = conspiracy.loyalists or {}

        rebel_total = sum(rebels.values()) if rebels else 0
        loyalist_total = king.army_size + sum(loyalists.values())

        if not sim_result:
            from bot.services.battle import simulate_combat
            sim_result = simulate_combat(rebel_total, loyalist_total)

        king_name = f"@{king.username}" if king.username else king.first_name

        if sim_result["winner"] == "attacker" and rebel_total > 0:
            conspiracy.status = "won"
            surviving = sim_result["atk_alive"]
            spoils = loyalist_total
            total_distribute = surviving + spoils

            for uid_str, commit in rebels.items():
                u = await get_user(session, int(uid_str))
                if u:
                    share = int(total_distribute * (commit / rebel_total))
                    u.army_size += share

            king.army_size = 1
            king.role = "lord"
            king_castles = await get_user_castles(session, king.user_id)
            non_crownlands = [c for c in king_castles if c.name != "Королівські Землі"]
            
            if non_crownlands:
                kept_castle = non_crownlands[0]
                for castle in king_castles:
                    if castle.castle_id != kept_castle.castle_id and castle.name != "Королівські Землі":
                        castle.owner_id = None
            else:
                for castle in king_castles:
                    if castle.name != "Королівські Землі":
                        castle.owner_id = None

            new_king_uid = max(rebels, key=rebels.get)
            new_king = await get_user(session, int(new_king_uid))
            if new_king:
                new_king.role = "king"
                new_king_name = f"@{new_king.username}" if new_king.username else new_king.first_name
                crown_res = await session.execute(select(Castle).where(Castle.name == "Королівські Землі"))
                crown_castle = crown_res.scalar_one_or_none()
                if crown_castle:
                    crown_castle.owner_id = new_king.user_id
            else:
                new_king_name = "Невідомий Лорд"

            text = f"⚔️ <b>ВЕЛИКА ЗМОВА ВДАЛАСЯ!</b>\n\nПовстанці здолали лоялістів та повалили Короля {king_name}!\n\n👑 Новий Король: {new_king_name}\n💪 Вижило повстанців: {sim_result['atk_alive']}\n🛡️ Втрати Корони: {sim_result['def_losses']}\n\n🩸 <i>Лоялісти та Король втратили всі надіслані війська. Повстанці розділили їх як трофеї!</i>"
        else:
            conspiracy.status = "failed"
            surviving = sim_result["def_alive"]
            spoils = rebel_total
            total_distribute = surviving + spoils

            king_commit = king.army_size
            king.army_size = 0

            if loyalist_total > 0:
                for uid_str, commit in loyalists.items():
                    u = await get_user(session, int(uid_str))
                    if u:
                        share = int(total_distribute * (commit / loyalist_total))
                        u.army_size += share

                king_share = int(total_distribute * (king_commit / loyalist_total))
                king.army_size += king_share
            else:
                king.army_size = 1

            text = f"🛡️ <b>ЗМОВУ ПРИДУШЕНО!</b>\n\nКороль {king_name} та лоялісти успішно відбили заколот!\n\n💪 Вижило лоялістів: {sim_result['def_alive']}\n⚔️ Втрати повстанців: {sim_result['atk_losses']}\n\n🩸 <i>Повстанці втратили всі надіслані війська. Лоялісти розділили їх як трофеї!</i>"

        await session.commit()

        try:
            from config.config import CHAT_ID
            await bot.send_message(chat_id=CHAT_ID, text=text)
        except Exception:
            logger.exception("Failed to send conspiracy result message to group")

async def resolve_conspiracy(conspiracy_id: int, bot: Bot) -> None:
    """
    Called when the voting timer expires. Starts the battle phase.
    """
    import asyncio
    async with AsyncSessionLocal() as session:
        conspiracy = await session.get(Conspiracy, conspiracy_id)
        if not conspiracy or conspiracy.status != "active":
            return

        king = await get_king(session)
        if not king:
            conspiracy.status = "failed"
            await session.commit()
            return
            
        conspiracy.status = "battling"
        await session.commit()

        rebels = conspiracy.rebels or {}
        loyalists = conspiracy.loyalists or {}
        rebel_total = sum(rebels.values()) if rebels else 0
        loyalist_total = king.army_size + sum(loyalists.values())

        rebel_power = rebel_total * random.uniform(0.8, 1.2)
        loyalist_power = loyalist_total * random.uniform(0.8, 1.2)
        king_name = f"@{king.username}" if king.username else king.first_name

        try:
            from config.config import CHAT_ID
            from bot.services.battle import simulate_combat
            
            sim_result = simulate_combat(rebel_total, loyalist_total)
            
            rebel_chance = int((rebel_total / (rebel_total + loyalist_total)) * 100) if (rebel_total + loyalist_total) > 0 else 50
            
            text = f"🏰 <b>БІЙ ЗА ЗАЛІЗНИЙ ТРОН РОЗПОЧАВСЯ!</b>\n\nВійська повстанців атакують браму!\n\nКороль: {king_name}\nШанс повстанців: {rebel_chance}%\nШанс Корони: {100 - rebel_chance}%\n\n<i>Очікуйте завершення бою...</i>"
            
            msg = await bot.send_message(chat_id=CHAT_ID, text=text)
            
            # Start the background task for dynamic updates
            asyncio.create_task(run_conspiracy_battle(conspiracy_id, bot, CHAT_ID, msg.message_id, rebel_total, loyalist_total, king_name, sim_result))
        except Exception:
            logger.exception("Failed to start conspiracy battle message")
            # Fallback directly to finish
            await finish_conspiracy(conspiracy_id, bot, sim_result)


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
        duration=CONSPIRACY_DURATION_MINUTES,
    )
