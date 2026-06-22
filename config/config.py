"""
ThroneChat — Configuration Module
Loads environment variables from .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


# === Telegram Bot ===
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
CHAT_ID: int = int(os.getenv("CHAT_ID", "0"))

# === WebApp Server ===
WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT: int = int(os.getenv("WEBAPP_PORT", "8080"))
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")

# === Database ===
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./thronebot.db")
DATABASE_URL: str = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# === Logging ===
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# ═══════════════════════════════════════════════
# ⚔️  GAME BALANCE CONSTANTS — DO NOT CHANGE
#     without explicit user approval
# ═══════════════════════════════════════════════

# Economy
ECONOMY_INTERVAL_MINUTES: int = 3 # minutes between economy ticks
DAILY_INTERVAL_MINUTES: int = 5 # minutes between daily ticks
POLL_INTERVAL_MINUTES: int = 5  # minutes between poll ticks
BASE_INCOME: int = 5               # troops/hr with no castles
CASTLE_INCOME: int = 10            # troops/hr per owned castle
BASE_ARMY_CAP: int = 500           # minimum army cap
CASTLE_ARMY_CAP: int = 500         # extra cap per castle
STARTING_ARMY: int = 100           # army size on registration

# Battle
MIN_ATTACK_ARMY: int = 100         # Minimum troops required to attack
BATTLE_TICK_DMG_MIN: float = 0.08  # Min % damage dealt per tick (8%)
BATTLE_TICK_DMG_MAX: float = 0.15  # Max % damage dealt per tick (15%)
BATTLE_RESOLVE_MINUTES: int = 5    # minutes until battle resolves (also ticks)

# Conspiracy
CONSPIRACY_DURATION_MINUTES: int = 20 # minutes for rebellion to form
CONSPIRACY_REBEL_DEFAULT_PCT: float = 0.50 # default army % committed by rebels

# King powers
MUTE_DURATION_MINUTES: int = 10    # default dungeon time


def validate_config() -> list[str]:
    """Check that all required config values are set. Returns list of errors."""
    errors = []
    if not BOT_TOKEN or BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        errors.append("BOT_TOKEN is not set or still uses the example value")
    if CHAT_ID == 0:
        errors.append("CHAT_ID is not set")
    if not BOT_USERNAME:
        errors.append("BOT_USERNAME is not set")
    return errors
