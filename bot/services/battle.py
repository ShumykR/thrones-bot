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
    User,
    count_user_castles,
    get_army_cap,
    get_user,
    get_user_castles,
)
from bot.texts import messages as msg
from config.config import (
    BATTLE_RAND_MAX,
    BATTLE_RAND_MIN,
    CHAT_ID,
)

logger = logging.getLogger(__name__)


def calculate_battle(attacker_army: int, defender_army: int) -> dict:
    """
    Calculate battle outcome with randomized power coefficients.

    Random coefficient: 0.8 – 1.2 applied to both sides.
    Winner/loser loss ranges differ to reward the victor.

    Returns dict with: winner, atk_power, def_power, atk_losses, def_losses.
    """
    atk_power = attacker_army * random.uniform(BATTLE_RAND_MIN, BATTLE_RAND_MAX)
    def_power = defender_army * random.uniform(BATTLE_RAND_MIN, BATTLE_RAND_MAX)

    if atk_power > def_power:
        winner = "attacker"
        atk_losses = int(attacker_army * random.uniform(0.20, 0.35))
        def_losses = int(defender_army * random.uniform(0.50, 0.70))
    else:
        winner = "defender"
        atk_losses = int(attacker_army * random.uniform(0.45, 0.60))
        def_losses = int(defender_army * random.uniform(0.20, 0.35))

    return {
        "winner": winner,
        "atk_power": round(atk_power),
        "def_power": round(def_power),
        "atk_losses": atk_losses,
        "def_losses": def_losses,
    }


async def resolve_battle(battle_id: int, bot: Bot) -> None:
    """
    Resolve a pending battle: calculate result, apply losses,
    transfer castle if attacker won, check puppet trigger.
    Called by APScheduler 5 minutes after battle start.
    """
    async with AsyncSessionLocal() as session:
        battle = await session.get(Battle, battle_id)
        if not battle or battle.status != "pending":
            logger.warning("Battle %s not found or already resolved", battle_id)
            return

        attacker = await session.get(User, battle.attacker_id)
        defender = await session.get(User, battle.defender_id)
        castle = await session.get(Castle, battle.castle_id)

        if not all([attacker, defender, castle]):
            logger.error("Battle %s: missing attacker/defender/castle", battle_id)
            battle.status = "done"
            await session.commit()
            return

        # Calculate battle outcome
        result = calculate_battle(battle.attacker_army, defender.army_size)

        # Apply losses (never reduce to 0 — minimum is 1)
        attacker.army_size = max(1, attacker.army_size - result["atk_losses"])
        defender.army_size = max(1, defender.army_size - result["def_losses"])

        # Record battle result
        battle.status = "done"
        battle.resolved_at = datetime.utcnow()
        battle.attacker_losses = result["atk_losses"]
        battle.defender_losses = result["def_losses"]

        # Format names for messages
        atk_name = f"@{attacker.username}" if attacker.username else attacker.first_name
        def_name = f"@{defender.username}" if defender.username else defender.first_name

        if result["winner"] == "attacker":
            # Attacker wins — transfer castle
            battle.winner_id = attacker.user_id
            castle.owner_id = attacker.user_id

            text = msg.BATTLE_RESULT_ATTACKER_WON.format(
                attacker_name=atk_name,
                defender_name=def_name,
                castle_name=castle.name,
                atk_power=result["atk_power"],
                def_power=result["def_power"],
                atk_losses=result["atk_losses"],
                def_losses=result["def_losses"],
            )

            # Check if defender lost their last castle → puppet trigger
            defender_castle_count = await count_user_castles(session, defender.user_id)
            if defender_castle_count == 0 and defender.role != "puppet":
                defender.role = "puppet"
                defender.master_id = attacker.user_id
                defender.independence_points = 0
                text += msg.BATTLE_PUPPET_TRIGGERED.format(
                    loser_name=def_name,
                    winner_name=atk_name,
                )
                logger.info(
                    "Puppet trigger: %s is now puppet of %s",
                    defender.user_id, attacker.user_id,
                )
        else:
            # Defender wins — castle stays
            battle.winner_id = defender.user_id

            text = msg.BATTLE_RESULT_DEFENDER_WON.format(
                attacker_name=atk_name,
                defender_name=def_name,
                castle_name=castle.name,
                atk_power=result["atk_power"],
                def_power=result["def_power"],
                atk_losses=result["atk_losses"],
                def_losses=result["def_losses"],
            )

        await session.commit()

        # Edit the live battle message with result
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
            logger.exception("Failed to edit/send battle result message")
            # Fallback: try sending a new message
            try:
                await bot.send_message(chat_id=CHAT_ID, text=text)
            except Exception:
                logger.exception("Failed to send fallback battle result message")

        logger.info(
            "Battle %s resolved: %s won (atk=%s def=%s)",
            battle_id, result["winner"],
            result["atk_power"], result["def_power"],
        )
