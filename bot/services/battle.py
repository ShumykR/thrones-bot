"""
ThroneChat — Battle Service
Core battle calculations and resolution logic.
"""

import logging
import random
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot

from bot.models.db import (
    AsyncSessionLocal,
    Battle,
    Castle,
    User
)
from bot.texts import messages as msg
from config.config import CHAT_ID

logger = logging.getLogger(__name__)


def simulate_combat(atk_army: int, def_army: int, ticks: int = 5) -> dict:
    """
    Iteratively simulate combat over a number of ticks.
    Returns history of states and final result.
    """
    history = []
    current_atk = atk_army
    current_def = def_army
    
    for _ in range(ticks):
        if current_atk <= 0 or current_def <= 0:
            break
            
        # Using configured damage percentages
        from config.config import BATTLE_TICK_DMG_MIN, BATTLE_TICK_DMG_MAX
        atk_dmg = current_atk * random.uniform(BATTLE_TICK_DMG_MIN, BATTLE_TICK_DMG_MAX)
        def_dmg = current_def * random.uniform(BATTLE_TICK_DMG_MIN, BATTLE_TICK_DMG_MAX)
        
        current_atk = max(0, int(current_atk - def_dmg))
        current_def = max(0, int(current_def - atk_dmg))
        
        history.append({
            "atk_alive": current_atk,
            "def_alive": current_def,
            "atk_losses": atk_army - current_atk,
            "def_losses": def_army - current_def
        })
        
    winner = "attacker" if current_atk > current_def else "defender"
    
    return {
        "history": history,
        "winner": winner,
        "atk_alive": current_atk,
        "def_alive": current_def,
        "atk_losses": atk_army - current_atk,
        "def_losses": def_army - current_def
    }


async def run_live_battle_updates(battle_id: int, bot: Bot, chat_id: int, msg_id: int, atk_army: int, def_army: int, atk_name: str, def_name: str, castle_name: str, simulation: dict) -> None:
    import asyncio
    
    def make_progress_bar(percent: int, length: int = 15) -> str:
        filled = int((percent / 100) * length)
        return "█" * filled + "░" * (length - filled)
        
    history = simulation["history"]
    for i, state in enumerate(history, 1):
        await asyncio.sleep(60)
        
        total_alive = state["atk_alive"] + state["def_alive"]
        atk_chance = int((state["atk_alive"] / total_alive) * 100) if total_alive > 0 else 50
        progress = make_progress_bar(atk_chance)
        
        text = (
            f"⚔️ <b>ШТУРМ ЗАМКУ {castle_name.upper()} ТРИВАЄ! (Хвилина {i}/5)</b>\n\n"
            f"🗡️ <b>Атакуючі ({atk_name}):</b>\n"
            f"В строю: {state['atk_alive']} воїнів\n"
            f"Втрати: {state['atk_losses']} воїнів\n\n"
            f"🛡️ <b>Захисники ({def_name}):</b>\n"
            f"В строю: {state['def_alive']} воїнів\n"
            f"Втрати: {state['def_losses']} воїнів\n\n"
            f"📊 <b>Перевага:</b>\n"
            f"Атака <code>[{progress}]</code> Захист\n"
            f"({atk_chance}% / {100 - atk_chance}%)\n\n"
            f"<i>Очікуйте завершення бою...</i>"
        )
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="HTML")
        except Exception:
            pass

    # Proceed to final resolution
    await resolve_battle(battle_id, bot, simulation)


async def resolve_battle(battle_id: int, bot: Bot, precalculated_sim: dict = None) -> None:
    """
    Resolve a pending battle: apply precalculated losses,
    transfer castle if attacker won.
    Called by run_live_battle_updates after 5 mins, or by APScheduler fallback.
    """
    async with AsyncSessionLocal() as session:
        battle = await session.get(Battle, battle_id)
        if not battle or battle.status != "pending":
            return

        attacker = await session.get(User, battle.attacker_id)
        defender = await session.get(User, battle.defender_id)
        castle = await session.get(Castle, battle.castle_id)

        if not all([attacker, defender, castle]):
            battle.status = "done"
            await session.commit()
            return

        if precalculated_sim:
            result = precalculated_sim
        else:
            result = simulate_combat(battle.attacker_army, castle.garrison or 0)

        # Apply losses
        attacker.army_size = max(1, attacker.army_size - result["atk_losses"])
        castle.garrison = max(0, (castle.garrison or 0) - result["def_losses"])

        battle.status = "done"
        battle.resolved_at = datetime.utcnow()
        battle.attacker_losses = result["atk_losses"]
        battle.defender_losses = result["def_losses"]

        atk_name = f"@{attacker.username}" if attacker.username else attacker.first_name
        def_name = f"@{defender.username}" if defender.username else defender.first_name

        if result["winner"] == "attacker":
            battle.winner_id = attacker.user_id
            castle.owner_id = attacker.user_id

            text = msg.BATTLE_RESULT_ATTACKER_WON.format(
                attacker_name=atk_name,
                defender_name=def_name,
                castle_name=castle.name,
                atk_power=result["atk_alive"],
                def_power=result["def_alive"],
                atk_losses=result["atk_losses"],
                def_losses=result["def_losses"],
            )
        else:
            battle.winner_id = defender.user_id

            text = msg.BATTLE_RESULT_DEFENDER_WON.format(
                attacker_name=atk_name,
                defender_name=def_name,
                castle_name=castle.name,
                atk_power=result["atk_alive"],
                def_power=result["def_alive"],
                atk_losses=result["atk_losses"],
                def_losses=result["def_losses"],
            )

        await session.commit()

        try:
            if battle.message_id:
                await bot.edit_message_text(
                    chat_id=CHAT_ID,
                    message_id=battle.message_id,
                    text=text,
                )
            else:
                await bot.send_message(chat_id=CHAT_ID, text=text)
        except Exception:
            try:
                await bot.send_message(chat_id=CHAT_ID, text=text)
            except Exception:
                pass
