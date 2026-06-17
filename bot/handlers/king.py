"""
ThroneChat — King Handlers
Commands for the King: /mute, /punish, /decree
"""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func

from bot.models.db import AsyncSessionLocal, User, Castle, get_user
from bot.services.king import king_mute
from bot.texts import messages as msg
from config.config import CHAT_ID

logger = logging.getLogger(__name__)

router = Router(name="king")


@router.message(Command("mute"))
async def mute_handler(message: Message, bot: Bot) -> None:
    """
    Handle /mute @username
    Only the King can use this command.
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("👑 Формат: <code>/mute @username</code>")
        return

    target_username = args[1].lstrip("@")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(func.lower(User.username) == target_username.lower())
        )
        target = result.scalar_one_or_none()

        if not target:
            await message.reply(f"⚔️ Лорд <b>@{target_username}</b> не знайдений у Великій Книзі!")
            return

        result_text = await king_mute(
            bot=bot,
            session=session,
            king_id=message.from_user.id,
            target_id=target.user_id,
        )
        await message.reply(result_text)


@router.message(Command("decree"))
async def decree_handler(message: Message, bot: Bot) -> None:
    """
    Handle /decree text
    Only the King can use this to send a royal decree to the chat.
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("👑 Формат: <code>/decree текст указу</code>")
        return

    decree_text = args[1]

    async with AsyncSessionLocal() as session:
        king = await get_user(session, message.from_user.id)
        if not king or king.role != "king":
            await message.reply(msg.ERR_NOT_KING)
            return

        king_name = f"@{king.username}" if king.username else king.first_name
        
        decree_msg = msg.KING_DECREE.format(
            king_name=king_name,
            decree_text=decree_text
        )
        
        await bot.send_message(CHAT_ID, decree_msg)
        await message.reply("👑 Ваш указ було розіслано воронами по всьому королівству!")


@router.message(Command("punish"))
async def punish_handler(message: Message, bot: Bot) -> None:
    """
    Handle /punish @username
    Only the King can use this. Takes 1 castle from the target and gives it to the King.
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("👑 Формат: <code>/punish @username</code>")
        return

    target_username = args[1].lstrip("@")

    async with AsyncSessionLocal() as session:
        king = await get_user(session, message.from_user.id)
        if not king or king.role != "king":
            await message.reply(msg.ERR_NOT_KING)
            return

        result = await session.execute(
            select(User).where(func.lower(User.username) == target_username.lower())
        )
        target = result.scalar_one_or_none()

        if not target:
            await message.reply(f"⚔️ Лорд <b>@{target_username}</b> не знайдений у Великій Книзі!")
            return

        if target.user_id == king.user_id:
            await message.reply("👑 Король не може покарати самого себе!")
            return

        # Take one castle
        castles_result = await session.execute(
            select(Castle).where(Castle.owner_id == target.user_id)
        )
        castles = castles_result.scalars().all()
        
        if not castles:
            await message.reply(f"У зрадника <b>@{target_username}</b> немає жодного замку для конфіскації.")
            return
            
        castle_to_take = castles[0]
        castle_to_take.owner_id = king.user_id
        
        await session.commit()
        
        target_name = f"@{target.username}" if target.username else target.first_name
        king_name = f"@{king.username}" if king.username else king.first_name
        
        punish_msg = (
            f"⚖️ <b>КОРОЛІВСЬКА КАРА</b>\n\n"
            f"Король <b>{king_name}</b> визнав <b>{target_name}</b> зрадником Короної!\n"
            f"🏰 Замок <b>{castle_to_take.name}</b> було конфісковано на користь Залізного Трону."
        )
        await bot.send_message(CHAT_ID, punish_msg)
