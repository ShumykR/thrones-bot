"""
ThroneChat — Inline Keyboards
All InlineKeyboardMarkup and CallbackData definitions.
"""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# ═══════════════════════════════════════
# Callback Data Classes
# ═══════════════════════════════════════

class ConspiracyVoteCallback(CallbackData, prefix="conspiracy"):
    """Callback for conspiracy voting buttons."""
    action: str           # 'rebel' | 'loyalist' | 'neutral'
    conspiracy_id: int


class EventClaimCallback(CallbackData, prefix="event"):
    """Callback for random event claim buttons."""
    action: str           # 'claim'
    event_id: str


# ═══════════════════════════════════════
# Keyboard Builders
# ═══════════════════════════════════════

def conspiracy_keyboard(conspiracy_id: int) -> InlineKeyboardMarkup:
    """Build the conspiracy voting keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⚔️ Повстанці",
                callback_data=ConspiracyVoteCallback(
                    action="rebel", conspiracy_id=conspiracy_id
                ).pack(),
            ),
            InlineKeyboardButton(
                text="👑 Лоялісти",
                callback_data=ConspiracyVoteCallback(
                    action="loyalist", conspiracy_id=conspiracy_id
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🕊️ Нейтральний",
                callback_data=ConspiracyVoteCallback(
                    action="neutral", conspiracy_id=conspiracy_id
                ).pack(),
            ),
        ],
    ])


def event_treasure_keyboard(event_id: str) -> InlineKeyboardMarkup:
    """Build the treasure claim keyboard for first-click events."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💰 Забрати скарб!",
                callback_data=EventClaimCallback(
                    action="claim", event_id=event_id
                ).pack(),
            ),
        ],
    ])
