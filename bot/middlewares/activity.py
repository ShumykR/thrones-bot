"""
ThroneChat — Activity Tracking Middleware
Counts group messages for puppet users.
Every PUPPET_MSG_THRESHOLD (50) messages → +PUPPET_MSG_IP (1) independence point.
Garrison freeze: if master has garrisoned castles, IP gain is blocked.
"""

import logging

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.models.db import AsyncSessionLocal, get_user, get_user_castles
from config.config import (
    GARRISON_FREEZES_IP,
    PUPPET_MSG_IP,
    PUPPET_MSG_THRESHOLD,
)

logger = logging.getLogger(__name__)


class ActivityTrackingMiddleware(BaseMiddleware):
    """
    Outer middleware that listens to ALL group messages.
    For puppet users:
    - Increments activity_count
    - Every 50 messages → +1 IP (if no garrison freeze)
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        # Only process regular messages with a sender
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        try:
            async with AsyncSessionLocal() as session:
                user = await get_user(session, user_id)

                # Only track puppets
                if user and user.role == "puppet":
                    user.activity_count += 1

                    # Check if threshold reached
                    if user.activity_count % PUPPET_MSG_THRESHOLD == 0:
                        # Check garrison freeze
                        should_grant_ip = True

                        if GARRISON_FREEZES_IP and user.master_id:
                            master_castles = await get_user_castles(
                                session, user.master_id
                            )
                            if any(c.garrison > 0 for c in master_castles):
                                should_grant_ip = False
                                logger.debug(
                                    "IP frozen for puppet %d — master has garrison",
                                    user_id,
                                )

                        if should_grant_ip:
                            user.independence_points = min(
                                100, user.independence_points + PUPPET_MSG_IP
                            )
                            logger.info(
                                "Activity IP: puppet %d reached %d messages → "
                                "+%d IP (total: %d)",
                                user_id,
                                user.activity_count,
                                PUPPET_MSG_IP,
                                user.independence_points,
                            )

                    await session.commit()

        except Exception:
            logger.exception(
                "Activity middleware error for user %d", user_id
            )

        # Always proceed to the next handler
        return await handler(event, data)
