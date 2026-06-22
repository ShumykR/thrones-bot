"""
ThroneChat — Common Handlers
/start, /help, /throne, /my_status
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from bot.models.db import (
    AsyncSessionLocal,
    User,
    get_or_create_user,
    get_king,
    get_user,
    get_user_castles,
    get_army_cap,
    count_user_castles,
)
from bot.texts import messages as msg
from config.config import CHAT_ID

logger = logging.getLogger(__name__)

router = Router(name="common")


# ═══════════════════════════════════════
# /start — Registration + Deep Link support
# ═══════════════════════════════════════

@router.message(CommandStart(deep_link=True))
async def start_with_deeplink(message: Message, command: CommandObject) -> None:
    """Handle /start with deep link parameters (e.g., conspiracy)."""
    args = command.args or ""

    if args.startswith("conspiracy_"):
        # Extract chat_id from deep link: conspiracy_{chat_id}
        try:
            target_chat_id = int(args.split("_", 1)[1])
        except (ValueError, IndexError):
            await message.answer("❌ Невірне посилання на змову.")
            return

        from bot.handlers.conspiracy import handle_conspiracy_deeplink
        result = await handle_conspiracy_deeplink(
            user_id=message.from_user.id,
            chat_id=target_chat_id,
            bot=message.bot,
        )
        await message.answer(result)
        return

    # Default: register the user
    await _register_user(message)



@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Handle /start — register the user as a Lord."""
    await _register_user(message)


async def _register_user(message: Message) -> None:
    """Internal: register or greet a returning user."""
    async with AsyncSessionLocal() as session:
        user, created = await get_or_create_user(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.full_name or "Лорд",
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.types.web_app_info import WebAppInfo
        
        from config.config import WEBAPP_URL
        webapp_url = WEBAPP_URL or "https://your-ngrok-url.ngrok-free.app"

        # Telegram throws BUTTON_TYPE_INVALID if we send web_app in an inline keyboard in a group chat.
        if message.chat.type == "private":
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Відкрити Вестерос", web_app=WebAppInfo(url=webapp_url))]
            ])
        else:
            bot_me = await message.bot.get_me()
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Відкрити Вестерос (в ПП)", url=f"https://t.me/{bot_me.username}")]
            ])

        if created:
            logger.info(
                "New Lord registered: %s (@%s)",
                user.first_name, user.username,
            )
            
            from bot.models.db import Castle
            from sqlalchemy import select
            import random
            
            result = await session.execute(
                select(Castle).where(Castle.owner_id == None, Castle.name != "Королівські Землі")
            )
            free_castles = result.scalars().all()
            
            if free_castles:
                chosen_castle = random.choice(free_castles)
                chosen_castle.owner_id = user.user_id
                await session.commit()
                welcome_text = msg.WELCOME_PRIVATE.format(
                    first_name=user.first_name,
                    army_size=user.army_size,
                ) + f"\n\n🏰 Ви отримали свій перший замок: <b>{chosen_castle.name}</b>!"
            else:
                welcome_text = msg.WELCOME_PRIVATE.format(
                    first_name=user.first_name,
                    army_size=user.army_size,
                ) + "\n\n⚠️ На жаль, всі вільні замки у Вестеросі вже зайняті. Вам доведеться відвоювати собі дім або чекати нових земель!"

            await message.answer(welcome_text, reply_markup=markup)
        else:
            await message.answer(
                msg.WELCOME_ALREADY_REGISTERED.format(
                    first_name=user.first_name,
                ),
                reply_markup=markup
            )

@router.message()
async def debug_all_messages(message: Message) -> None:
    """Catch-all to debug if messages are reaching the bot."""
    logger.info("DEBUG MSG RECEIVED: %s in chat %s (type %s)", message.text, message.chat.id, message.chat.type)

