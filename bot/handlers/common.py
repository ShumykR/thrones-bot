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
            first_name=message.from_user.first_name or "Лорд",
        )

        if created:
            logger.info(
                "New Lord registered: %s (@%s)",
                user.first_name, user.username,
            )
            await message.answer(
                msg.WELCOME_PRIVATE.format(
                    first_name=user.first_name,
                    army_size=user.army_size,
                )
            )
        else:
            await message.answer(
                msg.WELCOME_ALREADY_REGISTERED.format(
                    first_name=user.first_name,
                )
            )


# ═══════════════════════════════════════
# /help — List available commands
# ═══════════════════════════════════════

@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Show the list of available commands."""
    await message.answer(msg.HELP_TEXT)


# ═══════════════════════════════════════
# /throne — Kingdom status (group chat)
# ═══════════════════════════════════════

@router.message(Command("throne"))
async def throne_handler(message: Message) -> None:
    """Show the current state of the kingdom."""
    async with AsyncSessionLocal() as session:
        king = await get_king(session)

        # Count stats
        from sqlalchemy import select, func
        from bot.models.db import Castle

        total_castles = await session.scalar(
            select(func.count(Castle.castle_id))
        )
        total_lords = await session.scalar(
            select(func.count(User.user_id)).where(User.role.in_(["lord", "king"]))
        )
        total_puppets = await session.scalar(
            select(func.count(User.user_id)).where(User.role == "puppet")
        )

        if king:
            text = msg.THRONE_STATUS.format(
                king_name=f"@{king.username}" if king.username else king.first_name,
                total_castles=total_castles or 0,
                total_lords=total_lords or 0,
                total_puppets=total_puppets or 0,
            )
        else:
            text = msg.THRONE_NO_KING.format(
                total_castles=total_castles or 0,
                total_lords=total_lords or 0,
            )

        # TODO: Add WebApp button when webapp is ready (Етап 4)
        await message.answer(text)


# ═══════════════════════════════════════
# /my_status — Player profile (private)
# ═══════════════════════════════════════

@router.message(Command("my_status"))
async def my_status_handler(message: Message) -> None:
    """Show the player's personal profile. Sent as a reply (later: in DM or WebApp)."""
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await message.answer(msg.ERR_NOT_REGISTERED)
            return

        castle_count = await count_user_castles(session, user.user_id)
        castles = await get_user_castles(session, user.user_id)
        army_cap = await get_army_cap(session, user.user_id)

        # Build castle list
        castle_list = ""
        if castles:
            castle_lines = [f"  • {c.name}" for c in castles]
            castle_list = "\n🏰 Замки:\n" + "\n".join(castle_lines) + "\n"

        # Puppet info
        puppet_info = ""
        if user.role == "puppet" and user.master_id:
            master = await get_user(session, user.master_id)
            master_name = f"@{master.username}" if master and master.username else "Невідомий"
            puppet_info = msg.PUPPET_STATUS_LINE.format(
                master_name=master_name,
                ip=user.independence_points,
            )

        # Alliance info
        alliance_info = ""
        if user.alliance_id and user.alliance:
            alliance_info = msg.ALLIANCE_STATUS_LINE.format(
                alliance_name=user.alliance.name,
            )

        # Role display
        role_display = {
            "lord": "⚔️ Лорд",
            "king": "👑 Король",
            "puppet": "⛓️ Маріонетка",
        }.get(user.role, user.role)

        text = msg.MY_STATUS.format(
            first_name=user.first_name,
            role=role_display,
            army_size=user.army_size,
            army_cap=army_cap,
            castle_count=castle_count,
            castle_list=castle_list,
            puppet_info=puppet_info,
            alliance_info=alliance_info,
        )

        await message.answer(text)


# ═══════════════════════════════════════
# /castles — View all castles in Westeros
# ═══════════════════════════════════════

@router.message(Command("castles"))
async def castles_handler(message: Message) -> None:
    """Show the list of all castles and their details (owner, garrison, income)."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from bot.models.db import Castle

        # Query all castles and eagerly load their owners
        result = await session.execute(
            select(Castle).options(joinedload(Castle.owner))
        )
        castles = result.scalars().all()

        if not castles:
            await message.answer("🏰 У Вестеросі поки немає відомих замків.")
            return

        lines = ["🏰 <b>Замки Вестеросу та їхній стан:</b>\n"]
        for castle in castles:
            if castle.owner:
                owner_name = f"@{castle.owner.username}" if castle.owner.username else castle.owner.first_name
                owner_str = f"володар: <b>{owner_name}</b>"
            else:
                owner_str = "<i>вільний замок</i>"

            lines.append(
                f"• <b>{castle.name}</b>\n"
                f"  └ {owner_str} | гарнізон: <code>{castle.garrison}</code> | приріст: <code>+{castle.army_per_hour}</code> воїнів/год"
            )

        await message.answer("\n".join(lines))

