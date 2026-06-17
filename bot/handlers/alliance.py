"""
ThroneChat — Alliance Handlers
/alliance_create, /alliance_invite, /alliance_leave, /alliance_info
"""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.keyboards.inline import AllianceInviteCallback, alliance_invite_keyboard
from bot.models.db import Alliance, AsyncSessionLocal, User, get_user
from config.config import CHAT_ID

logger = logging.getLogger(__name__)

router = Router(name="alliance")


# ═══════════════════════════════════════
# /alliance_create <назва>
# ═══════════════════════════════════════

@router.message(Command("alliance_create"))
async def alliance_create_handler(
    message: Message, command: CommandObject
) -> None:
    """Create a new alliance. The user becomes leader."""
    alliance_name = (command.args or "").strip()
    if not alliance_name:
        await message.answer(
            "📜 Вкажіть назву для вашої коаліції.\n"
            "Приклад: <code>/alliance_create Залізні Вовки</code>"
        )
        return

    if len(alliance_name) > 64:
        await message.answer("⚠️ Назва занадто довга! Максимум 64 символи.")
        return

    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(
                "📜 Ви ще не записані у Великій Книзі. Надішліть /start боту в ПП."
            )
            return

        # Already in an alliance?
        if user.alliance_id:
            await message.answer(
                "🤝 Ви вже перебуваєте в коаліції! "
                "Спершу покиньте її командою /alliance_leave."
            )
            return

        # Check name uniqueness
        existing = await session.execute(
            select(Alliance).where(Alliance.name == alliance_name)
        )
        if existing.scalar_one_or_none():
            await message.answer(
                f"⚠️ Коаліція з назвою «<b>{alliance_name}</b>» вже існує. "
                "Оберіть іншу назву."
            )
            return

        # Create alliance
        alliance = Alliance(
            name=alliance_name,
            leader_id=user.user_id,
        )
        session.add(alliance)
        await session.flush()  # Get alliance_id

        user.alliance_id = alliance.alliance_id
        await session.commit()

        logger.info(
            "Alliance created: '%s' (id=%d) by @%s",
            alliance_name, alliance.alliance_id, user.username,
        )

        await message.answer(
            f"🤝 <b>Коаліцію «{alliance_name}» засновано!</b>\n\n"
            f"👑 Ви — її Глава.\n"
            f"Запрошуйте союзників: <code>/alliance_invite @username</code>"
        )


# ═══════════════════════════════════════
# /alliance_invite @username
# ═══════════════════════════════════════

@router.message(Command("alliance_invite"))
async def alliance_invite_handler(
    message: Message, command: CommandObject, bot: Bot
) -> None:
    """Invite a user to the alliance. Only the leader can invite."""
    target_input = (command.args or "").strip()
    if not target_input:
        await message.answer(
            "📜 Вкажіть кого запросити.\n"
            "Приклад: <code>/alliance_invite @username</code>"
        )
        return

    target_username = target_input.lstrip("@").lower()

    async with AsyncSessionLocal() as session:
        # Verify inviter
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(
                "📜 Ви ще не записані у Великій Книзі. Надішліть /start боту в ПП."
            )
            return

        if not user.alliance_id:
            await message.answer(
                "🤝 Ви не перебуваєте в жодній коаліції. "
                "Створіть свою: <code>/alliance_create назва</code>"
            )
            return

        alliance = await session.get(Alliance, user.alliance_id)
        if not alliance or alliance.leader_id != user.user_id:
            await message.answer(
                "👑 Лише Глава коаліції може надсилати запрошення!"
            )
            return

        # Find target by username
        result = await session.execute(
            select(User).where(
                User.username.ilike(target_username)
            )
        )
        target = result.scalar_one_or_none()

        if not target:
            await message.answer(
                f"⚠️ Лорда <b>@{target_username}</b> не знайдено у Великій Книзі."
            )
            return

        if target.user_id == user.user_id:
            await message.answer("🤦 Ви не можете запросити самого себе!")
            return

        if target.alliance_id:
            if target.alliance_id == user.alliance_id:
                await message.answer(
                    f"🤝 <b>@{target_username}</b> вже у вашій коаліції!"
                )
            else:
                await message.answer(
                    f"⚠️ <b>@{target_username}</b> вже присягнув іншій коаліції."
                )
            return

        # Send invite to target via DM
        invite_text = (
            f"📯 <b>Запрошення до Коаліції!</b>\n\n"
            f"Глава <b>@{user.username or user.first_name}</b> "
            f"запрошує вас до коаліції «<b>{alliance.name}</b>».\n\n"
            f"Оберіть свою долю, Лорде:"
        )

        try:
            await bot.send_message(
                chat_id=target.user_id,
                text=invite_text,
                reply_markup=alliance_invite_keyboard(alliance.alliance_id),
            )
            await message.answer(
                f"📯 Запрошення надіслано <b>@{target_username}</b> у приватні повідомлення."
            )
            logger.info(
                "Alliance invite sent: '%s' -> @%s (alliance=%d)",
                user.username, target_username, alliance.alliance_id,
            )
        except Exception:
            logger.exception("Failed to send alliance invite to %s", target.user_id)
            await message.answer(
                f"⚠️ Не вдалося надіслати запрошення <b>@{target_username}</b>.\n"
                "Можливо, Лорд ще не написав боту /start у ПП."
            )


# ═══════════════════════════════════════
# Callback: accept / decline invite
# ═══════════════════════════════════════

@router.callback_query(AllianceInviteCallback.filter())
async def alliance_invite_callback(
    query: CallbackQuery, callback_data: AllianceInviteCallback, bot: Bot
) -> None:
    """Handle accept/decline inline buttons for alliance invites."""
    await query.answer()

    action = callback_data.action
    alliance_id = callback_data.alliance_id

    async with AsyncSessionLocal() as session:
        user = await get_user(session, query.from_user.id)
        if not user:
            try:
                await query.message.edit_text(
                    "📜 Ви ще не записані у Великій Книзі. Надішліть /start."
                )
            except Exception:
                logger.exception("Failed to edit invite message")
            return

        alliance = await session.get(Alliance, alliance_id)
        if not alliance:
            try:
                await query.message.edit_text(
                    "⚠️ Цієї коаліції більше не існує. Вона була розпущена."
                )
            except Exception:
                logger.exception("Failed to edit invite message")
            return

        if action == "decline":
            try:
                await query.message.edit_text(
                    f"❌ Ви відхилили запрошення до коаліції «<b>{alliance.name}</b>».\n"
                    "Шлях одинокого вовка — теж шлях честі."
                )
            except Exception:
                logger.exception("Failed to edit invite message")

            # Notify the leader
            try:
                leader_name = f"@{user.username}" if user.username else user.first_name
                await bot.send_message(
                    chat_id=alliance.leader_id,
                    text=f"❌ <b>{leader_name}</b> відхилив запрошення "
                         f"до коаліції «<b>{alliance.name}</b>».",
                )
            except Exception:
                logger.exception("Failed to notify alliance leader %d", alliance.leader_id)
            return

        # action == "accept"
        if user.alliance_id:
            try:
                await query.message.edit_text(
                    "🤝 Ви вже перебуваєте в коаліції! "
                    "Спершу покиньте її командою /alliance_leave."
                )
            except Exception:
                logger.exception("Failed to edit invite message")
            return

        user.alliance_id = alliance.alliance_id
        await session.commit()

        logger.info(
            "User @%s joined alliance '%s' (id=%d)",
            user.username, alliance.name, alliance.alliance_id,
        )

        try:
            await query.message.edit_text(
                f"🤝 <b>Присягу прийнято!</b>\n\n"
                f"Відтепер ви — член коаліції «<b>{alliance.name}</b>».\n"
                f"Нехай союз зміцнить ваші землі! ⚔️"
            )
        except Exception:
            logger.exception("Failed to edit invite message")

        # Notify the leader
        try:
            joiner_name = f"@{user.username}" if user.username else user.first_name
            await bot.send_message(
                chat_id=alliance.leader_id,
                text=f"✅ <b>{joiner_name}</b> прийняв присягу "
                     f"та вступив до коаліції «<b>{alliance.name}</b>»!",
            )
        except Exception:
            logger.exception("Failed to notify alliance leader %d", alliance.leader_id)


# ═══════════════════════════════════════
# /alliance_leave
# ═══════════════════════════════════════

@router.message(Command("alliance_leave"))
async def alliance_leave_handler(message: Message, bot: Bot) -> None:
    """Leave the alliance. If leader leaves, alliance is disbanded."""
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(
                "📜 Ви ще не записані у Великій Книзі. Надішліть /start боту в ПП."
            )
            return

        if not user.alliance_id:
            await message.answer("🤝 Ви не перебуваєте в жодній коаліції.")
            return

        alliance = await session.get(Alliance, user.alliance_id)
        if not alliance:
            # Orphaned alliance_id — clean up
            user.alliance_id = None
            await session.commit()
            await message.answer("🤝 Ви не перебуваєте в жодній коаліції.")
            return

        is_leader = alliance.leader_id == user.user_id
        alliance_name = alliance.name

        if is_leader:
            # Disband: remove alliance_id from all members
            result = await session.execute(
                select(User).where(User.alliance_id == alliance.alliance_id)
            )
            members = list(result.scalars().all())

            for member in members:
                member.alliance_id = None

            await session.delete(alliance)
            await session.commit()

            logger.info(
                "Alliance '%s' (id=%d) disbanded by leader @%s",
                alliance_name, alliance.alliance_id, user.username,
            )

            await message.answer(
                f"⚔️ <b>Коаліцію «{alliance_name}» розпущено!</b>\n\n"
                f"Глава покинув союз — усі присяги розірвано.\n"
                f"Колишніх {len(members)} членів звільнено від обов'язків."
            )

            # Notify former members (except leader)
            leader_name = f"@{user.username}" if user.username else user.first_name
            for member in members:
                if member.user_id == user.user_id:
                    continue
                try:
                    await bot.send_message(
                        chat_id=member.user_id,
                        text=f"⚠️ Коаліцію «<b>{alliance_name}</b>» розпущено!\n"
                             f"Глава <b>{leader_name}</b> покинув союз. "
                             f"Ви знову вільний Лорд.",
                    )
                except Exception:
                    logger.exception(
                        "Failed to notify member %d about alliance disband",
                        member.user_id,
                    )
        else:
            # Regular member leaves
            user.alliance_id = None
            await session.commit()

            logger.info(
                "User @%s left alliance '%s' (id=%d)",
                user.username, alliance_name, alliance.alliance_id,
            )

            await message.answer(
                f"🚪 Ви покинули коаліцію «<b>{alliance_name}</b>».\n"
                f"Шлях одинокого вовка обрано."
            )

            # Notify the leader
            try:
                leaver_name = f"@{user.username}" if user.username else user.first_name
                await bot.send_message(
                    chat_id=alliance.leader_id,
                    text=f"🚪 <b>{leaver_name}</b> покинув коаліцію "
                         f"«<b>{alliance_name}</b>».",
                )
            except Exception:
                logger.exception(
                    "Failed to notify leader %d about member leaving",
                    alliance.leader_id,
                )


# ═══════════════════════════════════════
# /alliance_info
# ═══════════════════════════════════════

@router.message(Command("alliance_info"))
async def alliance_info_handler(message: Message) -> None:
    """Show alliance members and leader."""
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(
                "📜 Ви ще не записані у Великій Книзі. Надішліть /start боту в ПП."
            )
            return

        if not user.alliance_id:
            await message.answer(
                "🤝 Ви не перебуваєте в жодній коаліції.\n"
                "Створіть свою: <code>/alliance_create назва</code>"
            )
            return

        alliance = await session.get(Alliance, user.alliance_id)
        if not alliance:
            user.alliance_id = None
            await session.commit()
            await message.answer("🤝 Ви не перебуваєте в жодній коаліції.")
            return

        # Get all members
        result = await session.execute(
            select(User).where(User.alliance_id == alliance.alliance_id)
        )
        members = list(result.scalars().all())

        # Build member list
        member_lines = []
        for m in members:
            name = f"@{m.username}" if m.username else m.first_name
            if m.user_id == alliance.leader_id:
                member_lines.append(f"  👑 {name} — <i>Глава</i>")
            else:
                member_lines.append(f"  ⚔️ {name}")

        member_text = "\n".join(member_lines) if member_lines else "  (порожньо)"

        leader = await get_user(session, alliance.leader_id)
        leader_name = (
            f"@{leader.username}" if leader and leader.username else "Невідомий"
        )

        text = (
            f"🤝 <b>Коаліція «{alliance.name}»</b>\n\n"
            f"👑 Глава: <b>{leader_name}</b>\n"
            f"👥 Членів: <b>{len(members)}</b>\n\n"
            f"📜 <b>Склад:</b>\n{member_text}"
        )

        await message.answer(text)
