"""
ThroneChat — Antiflood Middleware
Prevents spamming inline buttons (throttling).
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject
from cachetools import TTLCache

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 2.0):
        # Cache stores user_id as key, value is arbitrary. TTL is the rate limit.
        self.cache = TTLCache(maxsize=10_000, ttl=rate_limit)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        
        # We only throttle CallbackQuery (inline buttons) to prevent spamming
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            if user_id in self.cache:
                logger.debug("Throttled callback from user %s", user_id)
                # Answer the query to stop the loading circle on the client side
                await event.answer("⏳ Не так швидко, Лорде! Дайте воронам відпочити.", show_alert=False)
                return
            
            # Add to cache
            self.cache[user_id] = True

        return await handler(event, data)
