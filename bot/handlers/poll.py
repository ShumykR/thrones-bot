from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.db import AsyncSessionLocal, get_user
import logging

logger = logging.getLogger(__name__)

router = Router()

class PollOpinionCallback(CallbackData, prefix="poll"):
    opinion: str  # 'good' | 'bad' | 'neutral'

@router.callback_query(PollOpinionCallback.filter())
async def handle_poll_opinion(
    query: CallbackQuery, 
    callback_data: PollOpinionCallback,
) -> None:
    """Handle secret poll response."""
    user_id = query.from_user.id
    opinion = callback_data.opinion
    
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            await query.answer("Вас немає у Великій Книзі!")
            return
            
        if user.role == "king":
            await query.answer("Ви Король, ваша думка про себе не враховується.")
            return
            
        user.king_opinion = opinion
        await session.commit()
        
    labels = {
        'good': 'Хороша (Лояліст)',
        'bad': 'Погана (Бунтівник)',
        'neutral': 'Нейтральна'
    }
    await query.message.edit_text(f"Вашу таємну думку враховано: {labels.get(opinion, opinion)}!", reply_markup=None)
    await query.answer("Ваш голос враховано.")
