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
BASE_INCOME: int = 2               # troops/hr with no castles
CASTLE_INCOME: int = 10            # troops/hr per owned castle
BASE_ARMY_CAP: int = 500           # minimum army cap
CASTLE_ARMY_CAP: int = 500         # extra cap per castle
STARTING_ARMY: int = 100           # army size on registration

# Battle
MIN_ATTACK_ARMY: int = 100         # Minimum troops required to attack
BATTLE_RAND_MIN: float = 0.8       # battle randomness floor
BATTLE_RAND_MAX: float = 1.2       # battle randomness ceiling
BATTLE_RESOLVE_MINUTES: int = 5    # minutes until battle resolves

# Puppet system
PUPPET_TAX_RATE: float = 0.30      # 30% hourly income tax to master
PUPPET_DAILY_IP: int = 10          # independence points per day
PUPPET_MSG_IP: int = 1             # IP per 50 messages
PUPPET_MSG_THRESHOLD: int = 50     # messages needed for +1 IP
SABOTAGE_IP_GAIN: int = 15         # IP from /sabotage
MERCY_IP_REDUCTION: int = 20       # IP reduction from /mercy
REBEL_THRESHOLD: int = 100         # IP needed to attempt /rebel
GARRISON_FREEZES_IP: bool = True   # garrison prevents daily IP gain

# Conspiracy
CONSPIRACY_DURATION_H: int = 4     # hours for rebellion to form
CONSPIRACY_LOSER_PENALTY: float = 0.50  # rebels lose 50% army if king survives

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
