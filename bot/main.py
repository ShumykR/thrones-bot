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
from aiohttp import web

from config.config import BOT_TOKEN, LOG_LEVEL, WEBAPP_HOST, WEBAPP_PORT, CHAT_ID, validate_config
from bot.models.db import init_db
from bot.handlers.common import router as common_router
from bot.handlers.war import router as war_router
from bot.handlers.conspiracy import router as conspiracy_router
from bot.handlers.puppet import router as puppet_router
from bot.handlers.alliance import router as alliance_router
from bot.handlers.king import router as king_router
from bot.middlewares.activity import ActivityTrackingMiddleware
from bot.middlewares.antiflood import ThrottlingMiddleware
from bot.services.scheduler import setup_scheduler, scheduler
from bot.api import setup_api


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

    # Register middlewares
    dp.message.middleware(ActivityTrackingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())

    # Register routers
    dp.include_router(common_router)
    dp.include_router(war_router)
    dp.include_router(conspiracy_router)
    dp.include_router(puppet_router)
    dp.include_router(alliance_router)
    dp.include_router(king_router)

    # Start APScheduler (economy tick, daily tick)
    setup_scheduler(bot)
    logger.info("⏰ Scheduler started")

    # Start WebApp API Server
    app = setup_api()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logger.info(f"🌐 WebApp API started at http://{WEBAPP_HOST}:{WEBAPP_PORT}")

    logger.info("👑 Bot is ready! Starting polling...")

    # Check bot permissions in the chat
    try:
        bot_member = await bot.get_chat_member(chat_id=CHAT_ID, user_id=bot.id)
        if bot_member.status != "administrator":
            logger.warning(f"⚠️ Bot is NOT an administrator in chat {CHAT_ID}! Some features (like /mute) will fail.")
        else:
            logger.info("🛡️ Bot has administrator rights in the chat.")
    except Exception as e:
        logger.error(f"⚠️ Could not verify bot permissions in chat {CHAT_ID}. Is the bot added to the chat? Error: {e}")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
