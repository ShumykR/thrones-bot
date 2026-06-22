"""
ThroneChat — King Handlers
Commands for the King: /order
"""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func

from bot.models.db import AsyncSessionLocal, User, Castle, get_user
from bot.texts import messages as msg
from config.config import CHAT_ID
from bot.keyboards.inline import OrderCallback

logger = logging.getLogger(__name__)

router = Router(name="king")

@router.message(Command("order"))
async def order_handler(message: Message, bot: Bot) -> None:
    """
    Handle /order @username troops 500
    Handle /order @username castle Вінтерфелл
    """
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply("👑 Формат: <code>/order @username troops 500</code> або <code>/order @username castle Назва</code>")
        return

    target_username = args[1].lstrip("@")
    order_type = args[2].lower()
    value = args[3]

    if order_type not in ("troops", "castle", "give_troops", "give_castle"):
        await message.reply("👑 Невідомий тип наказу. Використовуйте 'troops', 'castle', 'give_troops', 'give_castle'.")
        return

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
            await message.reply("👑 Король не може наказати самому собі!")
            return

        from bot.keyboards.inline import order_keyboard
        king_name = f"@{king.username}" if king.username else king.first_name
        target_name = f"@{target.username}" if target.username else target.first_name
        
        # Handle Instant Gifts (Give)
        if order_type == "give_troops":
            try:
                amount = int(value)
            except ValueError:
                await message.reply("Невірне число.")
                return
            if king.army_size < amount:
                await message.reply("У вас недостатньо військ для подарунка!")
                return
            king.army_size -= amount
            target.army_size += amount
            await session.commit()
            
            gift_msg = f"🎁 <b>КОРОЛІВСЬКА МИЛІСТЬ</b>\n\nКороль <b>{king_name}</b> дарує <b>{target_name}</b> {amount} воїнів!"
            await bot.send_message(CHAT_ID, gift_msg)
            await message.reply("👑 Дарунок відправлено!")
            return
            
        elif order_type == "give_castle":
            castle_name = value
            result = await session.execute(
                select(Castle).where(Castle.owner_id == king.user_id, func.lower(Castle.name) == castle_name.lower())
            )
            castle = result.scalar_one_or_none()
            if not castle:
                await message.reply("У вас немає такого замку!")
                return
            
            castle.owner_id = target.user_id
            await session.commit()
            
            gift_msg = f"🎁 <b>КОРОЛІВСЬКА МИЛІСТЬ</b>\n\nКороль <b>{king_name}</b> дарує <b>{target_name}</b> замок <b>{castle.name}</b>!"
            await bot.send_message(CHAT_ID, gift_msg)
            await message.reply("👑 Дарунок відправлено!")
            return

        # Handle Demands
        if order_type == "troops":
            req_text = f"{value} воїнів"
            threat = "відібрання голосу (Mute) на добу!"
        else:
            req_text = f"замок {value}"
            threat = "конфіскацію випадкового замку та тавро бунтівника!"

        order_msg = (
            f"📜 <b>КОРОЛІВСЬКИЙ НАКАЗ</b>\n\n"
            f"Король <b>{king_name}</b> вимагає від <b>{target_name}</b> передати Короні <b>{req_text}</b>!\n\n"
            f"⚠️ Відмова означатиме <b>{threat}</b>"
        )
        
        await bot.send_message(CHAT_ID, order_msg, reply_markup=order_keyboard(target.user_id, order_type, value))
        await message.reply("👑 Ваш наказ було надіслано!")

@router.callback_query(OrderCallback.filter())
async def order_callback_handler(
    query: CallbackQuery,
    callback_data: OrderCallback,
    bot: Bot,
) -> None:
    user_id = query.from_user.id
    target_id = callback_data.target_id

    if user_id != target_id:
        await query.answer("Це повідомлення не для вас!", show_alert=True)
        return

    action = callback_data.action
    order_type = callback_data.order_type
    value = callback_data.value

    async with AsyncSessionLocal() as session:
        target = await get_user(session, target_id)
        
        result = await session.execute(select(User).where(User.role == "king"))
        king = result.scalar_one_or_none()
        
        if not king:
            await query.answer("Короля більше немає...", show_alert=True)
            await query.message.delete()
            return
            
        target_name = f"@{target.username}" if target.username else target.first_name

        if action == "accept":
            if order_type == "troops":
                try:
                    amount = int(value)
                except ValueError:
                    amount = 0
                if target.army_size < amount:
                    await query.answer("У вас недостатньо військ!", show_alert=True)
                    return
                target.army_size -= amount
                king.army_size += amount
                await session.commit()
                await query.message.edit_text(f"✅ <b>{target_name}</b> підкорився наказу і передав {amount} воїнів Короні.")
                
            elif order_type == "castle":
                castle_name = value
                result = await session.execute(
                    select(Castle).where(Castle.owner_id == target.user_id, func.lower(Castle.name) == castle_name.lower())
                )
                castle = result.scalar_one_or_none()
                if not castle:
                    await query.answer("У вас немає такого замку!", show_alert=True)
                    return
                castle.owner_id = king.user_id
                await session.commit()
                await query.message.edit_text(f"✅ <b>{target_name}</b> підкорився наказу і передав замок {castle.name} Короні.")
                
        elif action == "decline":
            if order_type == "troops":
                # Apply mute
                from bot.services.king import king_mute
                await king_mute(bot, session, king.user_id, target.user_id)
                await query.message.edit_text(f"❌ <b>{target_name}</b> відмовився виконувати Королівський наказ! За це його публічно засуджено і зашито рота.")
            else:
                # Confiscate random castle and mark as rebel
                castles_result = await session.execute(
                    select(Castle).where(Castle.owner_id == target.user_id)
                )
                castles = castles_result.scalars().all()
                if castles:
                    castle_to_take = castles[0]
                    castle_to_take.owner_id = king.user_id
                    target.king_opinion = 'bad'
                    await session.commit()
                    await query.message.edit_text(f"❌ <b>{target_name}</b> відмовився передати замок!\nКороль силоміць конфіскував <b>{castle_to_take.name}</b>. Лорда оголошено бунтівником!")
                else:
                    target.king_opinion = 'bad'
                    await session.commit()
                    await query.message.edit_text(f"❌ <b>{target_name}</b> відмовився передати замок!\nОскільки замків у нього немає, його просто оголошено бунтівником!")
