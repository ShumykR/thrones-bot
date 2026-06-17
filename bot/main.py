"""
ThroneChat — Main Entry Point
Starts the bot polling + APScheduler.
Run with: python -m bot.main
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.config import BOT_TOKEN, LOG_LEVEL, validate_config
from bot.models.db import init_db
from bot.handlers.common import router as common_router


def setup_logging() -> None:
    """Configure logging for the bot."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Quiet down noisy libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def main() -> None:
    """Initialize and start the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Validate configuration
    errors = validate_config()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        logger.error("Please fill in your .env file (see .env.example)")
        sys.exit(1)

    logger.info("⚔️  ThroneChat Bot starting...")

    # Initialize database
    await init_db()
    logger.info("🏰 Database initialized, castles seeded")

    # Create bot & dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(common_router)
    # Future routers will be added here:
    # dp.include_router(war_router)
    # dp.include_router(conspiracy_router)
    # dp.include_router(puppet_router)
    # dp.include_router(alliance_router)

    logger.info("👑 Bot is ready! Starting polling...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
