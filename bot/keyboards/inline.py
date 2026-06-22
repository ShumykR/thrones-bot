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


class AllianceInviteCallback(CallbackData, prefix="ally"):
    """Callback for alliance invite accept/decline buttons."""
    action: str           # 'accept' | 'decline'
    alliance_id: int


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


def alliance_invite_keyboard(alliance_id: int) -> InlineKeyboardMarkup:
    """Build the accept/decline keyboard for alliance invitations."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Прийняти присягу",
                callback_data=AllianceInviteCallback(
                    action="accept", alliance_id=alliance_id
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Відхилити",
                callback_data=AllianceInviteCallback(
                    action="decline", alliance_id=alliance_id
                ).pack(),
            ),
        ],
    ])

class OrderCallback(CallbackData, prefix="order"):
    action: str           # 'accept' | 'decline'
    target_id: int
    order_type: str       # 'troops' | 'castle'
    value: str            # amount or castle name

def order_keyboard(target_id: int, order_type: str, value: str) -> InlineKeyboardMarkup:
    """Build the accept/decline keyboard for royal orders."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Підкоритися",
                callback_data=OrderCallback(
                    action="accept", target_id=target_id, order_type=order_type, value=value
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Відмовитись (Кара)",
                callback_data=OrderCallback(
                    action="decline", target_id=target_id, order_type=order_type, value=value
                ).pack(),
            ),
        ],
    ])
