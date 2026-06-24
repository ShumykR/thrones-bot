"""
ThroneChat — WebApp API
REST API for the Telegram Mini App using aiohttp.
"""

import hashlib
import hmac
import json
import logging
import urllib.parse
from datetime import datetime
from pathlib import Path

from aiohttp import web
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from bot.models.db import AsyncSessionLocal, User, Castle, get_army_cap, get_user
from config.config import BOT_TOKEN, MIN_ATTACK_ARMY

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()
webapp_dir = Path(__file__).resolve().parent.parent / "webapp" / "dist"

def validate_init_data(init_data: str, token: str) -> dict | None:
    """Validate Telegram WebApp initData and return parsed user dict."""
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None
            
        hash_val = parsed_data.pop("hash")
        
        # Sort data
        sorted_data = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        # Calculate signature
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, sorted_data.encode(), hashlib.sha256).hexdigest()
        
        if calc_hash != hash_val:
            return None
            
        # Parse user json if present
        if "user" in parsed_data:
            return json.loads(parsed_data["user"])
            
        return None
    except Exception as e:
        logger.error("Error validating initData: %s", e)
        return None


@web.middleware
async def auth_middleware(request: web.Request, handler) -> web.Response:
    """Middleware to authenticate requests to /api/ using Telegram initData."""
    if request.path.startswith("/api/") and not request.path.startswith("/api/photo"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow OPTIONS for CORS
            if request.method == "OPTIONS":
                return await handler(request)
            return web.json_response({"error": "Missing or invalid Authorization header"}, status=401)
            
        init_data = auth_header.split(" ")[1]
        user_data = validate_init_data(init_data, BOT_TOKEN)
        
        if not user_data or "id" not in user_data:
            return web.json_response({"error": "Invalid initData"}, status=403)
            
        request["user_id"] = user_data["id"]
        
    return await handler(request)


@routes.get("/api/me")
async def api_me(request: web.Request) -> web.Response:
    """Get the current player's profile."""
    user_id = request["user_id"]
    
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
            
        castles_result = await session.execute(
            select(Castle).where(Castle.owner_id == user_id)
        )
        castles = castles_result.scalars().all()
        
        return web.json_response({
            "user_id": user.user_id,
            "username": user.username,
            "first_name": user.first_name,
            "role": user.role,
            "army_size": user.army_size,
            "king_tribute_rate": user.king_tribute_rate,
            "castles_count": len(castles),
            "castles": [{"id": c.castle_id, "name": c.name} for c in castles],
            "photo_url": f"/api/photo/{user.user_id}"
        })

@routes.get("/api/photo/{target_id}")
async def api_photo(request: web.Request) -> web.Response:
    target_id = int(request.match_info["target_id"])
    bot = request.app['bot']
    try:
        photos = await bot.get_user_profile_photos(target_id, limit=1)
        if photos.total_count > 0:
            # get the smallest photo
            file_id = photos.photos[0][0].file_id
            file = await bot.get_file(file_id)
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        return web.Response(body=content, content_type="image/jpeg")
    except Exception:
        pass
    
    # Return 404 or a default transparent image
    return web.Response(status=404)


@routes.get("/api/state")
async def api_state(request: web.Request) -> web.Response:
    """Get the full game state: all castles and their owners."""
    async with AsyncSessionLocal() as session:
        # Get all castles with owners
        result = await session.execute(
            select(Castle).options(joinedload(Castle.owner))
        )
        castles = result.scalars().all()
        
        # Get king
        king_result = await session.execute(select(User).where(User.role == "king"))
        king = king_result.scalar_one_or_none()
        
        king_data = None
        if king:
            king_data = {
                "id": king.user_id,
                "name": king.first_name,
                "authority": king.authority
            }
        
        castles_data = []
        for c in castles:
            owner_data = None
            if c.owner:
                owner_data = {
                    "id": c.owner.user_id,
                    "name": c.owner.first_name,
                    "username": c.owner.username
                }
                
            castles_data.append({
                "id": c.castle_id,
                "name": c.name,
                "garrison": c.garrison,
                "army_per_hour": c.army_per_hour,
                "owner": owner_data
            })
            
        # Get all users
        users_result = await session.execute(select(User))
        all_users = users_result.scalars().all()
        users_data = [{
            "id": u.user_id, 
            "name": u.first_name, 
            "username": u.username, 
            "role": u.role, 
            "alliance_id": u.alliance_id,
            "king_opinion": u.king_opinion,
            "army_size": u.army_size,
            "authority": u.authority,
            "king_tribute_rate": u.king_tribute_rate
        } for u in all_users]
        
        # Get active conspiracy
        from config.config import CHAT_ID
        from bot.models.db import Conspiracy
        conspiracy_res = await session.execute(
            select(Conspiracy).where(
                Conspiracy.chat_id == CHAT_ID,
                Conspiracy.status == "active"
            ))
        active_consp = conspiracy_res.scalar_one_or_none()
        conspiracy_data = None
        if active_consp:
            conspiracy_data = {
                "initiator_id": active_consp.initiator_id,
                "rebels": active_consp.rebels or {},
                "loyalists": active_consp.loyalists or {}
            }

        from bot.models.db import Alliance, ScoutReport
        from datetime import datetime, timedelta
        
        alliances_res = await session.execute(select(Alliance))
        all_alliances = alliances_res.scalars().all()
        alliances_data = [{
            "id": a.alliance_id,
            "name": a.name,
            "leader_id": a.leader_id
        } for a in all_alliances]
        
        scouted_castles = {}
        if "user_id" in request:
            user_id = request["user_id"]
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            reports_res = await session.execute(
                select(ScoutReport).where(
                    ScoutReport.user_id == user_id,
                    ScoutReport.timestamp >= cutoff_time
                )
            )
            reports = reports_res.scalars().all()
            for r in reports:
                scouted_castles[r.castle_id] = r.garrison

        return web.json_response({
            "king": king_data,
            "castles": castles_data,
            "users": users_data,
            "conspiracy": conspiracy_data,
            "alliances": alliances_data,
            "scouted_castles": scouted_castles,
            "config": {
                "min_attack_army": MIN_ATTACK_ARMY
            }
        })


@routes.post("/api/attack")
async def api_attack(request: web.Request) -> web.Response:
    """Initiate an attack from the WebApp."""
    user_id = request["user_id"]
    try:
        data = await request.json()
        castle_id = int(data.get("castle_id"))
        army_amount = int(data.get("amount"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return web.json_response({"error": "Invalid request data"}, status=400)

    async with AsyncSessionLocal() as session:
        attacker = await get_user(session, user_id)
        if not attacker:
            return web.json_response({"error": "User not found"}, status=404)

        if army_amount < MIN_ATTACK_ARMY:
            return web.json_response({"error": f"Мінімальна армія: {MIN_ATTACK_ARMY}"}, status=400)

        if army_amount > attacker.army_size:
            return web.json_response({"error": "Недостатньо воїнів"}, status=400)

        # Check active battle
        from bot.models.db import get_active_battle_for_user
        active_battle = await get_active_battle_for_user(session, attacker.user_id)
        if active_battle:
            return web.json_response({"error": "Ви вже у поході!"}, status=400)

        # Target castle
        target_castle = await session.get(Castle, castle_id)
        if not target_castle:
            return web.json_response({"error": "Замок не знайдено"}, status=404)

        if target_castle.owner_id == attacker.user_id:
            return web.json_response({"error": "Ви не можете атакувати власний замок!"}, status=400)

        # Defender
        if target_castle.owner_id is None:
            # Handle free castle
            target_castle.owner_id = attacker.user_id
            target_castle.garrison = (target_castle.garrison or 0) + army_amount
            attacker.army_size -= army_amount
            await session.commit()
            return web.json_response({"success": True, "message": f"Ви успішно зайняли вільний замок {target_castle.name}!"})
            
        defender = await session.get(User, target_castle.owner_id)
        if not defender:
            return web.json_response({"error": "Власника не знайдено"}, status=404)


        if attacker.alliance_id and defender.alliance_id and attacker.alliance_id == defender.alliance_id:
            return web.json_response({"error": "Не можна атакувати союзника!"}, status=400)

        # Apply battle start
        attacker.army_size -= army_amount

        from bot.models.db import Battle
        battle = Battle(
            attacker_id=attacker.user_id,
            defender_id=defender.user_id,
            castle_id=target_castle.castle_id,
            attacker_army=army_amount,
            started_at=datetime.utcnow(),
        )
        session.add(battle)
        await session.flush()

        from bot.texts import messages as msg
        from config.config import CHAT_ID
        atk_name = f"@{attacker.username}" if attacker.username else attacker.first_name
        def_name = f"@{defender.username}" if defender.username else defender.first_name

        announcement_text = msg.BATTLE_ANNOUNCED.format(
            attacker_name=atk_name,
            defender_name=def_name,
            army_sent=army_amount,
            castle_name=target_castle.name,
        )

        from aiogram import Bot
        from config.config import BOT_TOKEN
        # Need the bot instance... since we don't have it directly in the request, 
        # we can get it via a global or by importing it.
        # It's better to store bot instance in app.
        bot: Bot = request.app['bot']
        
        try:
            sent_msg = await bot.send_message(chat_id=CHAT_ID, text=announcement_text)
            battle.message_id = sent_msg.message_id
        except Exception:
            pass

        await session.commit()

        from bot.services.battle import simulate_combat, run_live_battle_updates, resolve_battle
        
        def_army = target_castle.garrison or 0
        
        # Precalculate simulation
        sim_result = simulate_combat(battle.attacker_army, def_army)
        
        if battle.message_id:
            import asyncio
            asyncio.create_task(run_live_battle_updates(
                battle.battle_id, bot, CHAT_ID, battle.message_id, 
                battle.attacker_army, def_army, 
                atk_name, def_name, target_castle.name, sim_result
            ))
        else:
            # If we couldn't send the first message, just resolve it asynchronously but instantly
            # or rely on scheduler fallback. Actually, let's schedule fallback.
            from bot.services.scheduler import schedule_battle_resolution
            schedule_battle_resolution(battle.battle_id, bot)

        return web.json_response({"success": True, "message": "Війська вирушили на штурм!"})
@routes.post("/api/conspiracy")
async def api_conspiracy(request: web.Request) -> web.Response:
    """Initiate a conspiracy."""
    user_id = request["user_id"]
    bot = request.app['bot']
    
    try:
        data = await request.json()
        amount = int(data.get("amount", 0))
    except Exception:
        amount = 0
    
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        if user.role == "king":
            return web.json_response({"error": "Король не може бунтувати!"}, status=400)
            
        min_amount = int(user.army_size * 0.70)
        if amount < min_amount:
            amount = min_amount

        from bot.services.conspiracy import start_conspiracy
        from config.config import CHAT_ID
        
        conspiracy = await start_conspiracy(session, CHAT_ID, user_id, bot, amount)
        if conspiracy:
            return web.json_response({"success": True, "message": "Змова розпочата! Перевірте бот."})
        else:
            return web.json_response({"error": "Не вдалося розпочати змову. Можливо, вона вже триває або ви не маєте прав."}, status=400)

@routes.post("/api/decree")
async def api_decree(request: web.Request) -> web.Response:
    user_id = request["user_id"]
    bot = request.app['bot']
    try:
        data = await request.json()
        text = data.get("text")
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)
        
    async with AsyncSessionLocal() as session:
        king = await get_user(session, user_id)
        if not king or king.role != "king":
            return web.json_response({"error": "Тільки Король може видавати укази"}, status=400)
            
        from bot.texts import messages as msg
        from config.config import CHAT_ID
        king_name = f"@{king.username}" if king.username else king.first_name
        decree_msg = msg.KING_DECREE.format(king_name=king_name, decree_text=text)
        
        await bot.send_message(CHAT_ID, decree_msg)
        return web.json_response({"message": "✅ Указ надіслано в чат!"})


@routes.post("/api/order")
async def api_order(request: web.Request) -> web.Response:
    """Send a royal order (troops or castle)."""
    user_id = request["user_id"]
    data = await request.json()
    target_id = data.get("target_id")
    order_type = data.get("order_type")
    value = data.get("value")

    if not target_id or order_type not in ("troops", "castle", "give_troops", "give_castle") or value is None or value == "":
        return web.json_response({"error": f"Missing parameters: target={target_id}, type={order_type}, value={value}"}, status=400)

    try:
        target_id = int(target_id)
    except ValueError:
        return web.json_response({"error": "Invalid target_id"}, status=400)

    bot = request.app['bot']
    async with AsyncSessionLocal() as session:
        king = await get_user(session, user_id)
        if not king or king.role != "king":
            return web.json_response({"error": "Тільки Король може віддавати накази!"}, status=403)

        target = await get_user(session, target_id)
        if not target:
            return web.json_response({"error": "Лорда не знайдено!"}, status=404)

        if target.user_id == king.user_id:
            return web.json_response({"error": "Король не може наказати самому собі!"}, status=400)

        from bot.keyboards.inline import order_keyboard
        from config.config import CHAT_ID
        king_name = f"@{king.username}" if king.username else king.first_name
        target_name = f"@{target.username}" if target.username else target.first_name
        
        # Handle Instant Gifts (Give)
        if order_type == "give_troops":
            try:
                amount = int(value)
            except ValueError:
                return web.json_response({"error": "Invalid amount"}, status=400)
            if king.army_size < amount:
                return web.json_response({"error": "У вас недостатньо військ для подарунка!"}, status=400)
            king.army_size -= amount
            target.army_size += amount
            await session.commit()
            
            gift_msg = f"🎁 <b>КОРОЛІВСЬКА МИЛІСТЬ</b>\n\nКороль <b>{king_name}</b> дарує <b>{target_name}</b> {amount} воїнів!"
            await bot.send_message(CHAT_ID, gift_msg)
            return web.json_response({"message": "✅ Війська успішно подаровано!"})
            
        elif order_type == "give_castle":
            castle_name = value
            result = await session.execute(
                select(Castle).where(Castle.owner_id == king.user_id, func.lower(Castle.name) == castle_name.lower())
            )
            castle = result.scalar_one_or_none()
            if not castle:
                return web.json_response({"error": "У вас немає такого замку!"}, status=400)
            
            castle.owner_id = target.user_id
            await session.commit()
            
            gift_msg = f"🎁 <b>КОРОЛІВСЬКА МИЛІСТЬ</b>\n\nКороль <b>{king_name}</b> дарує <b>{target_name}</b> замок <b>{castle.name}</b>!"
            await bot.send_message(CHAT_ID, gift_msg)
            return web.json_response({"message": f"✅ Замок {castle.name} успішно подаровано!"})

        # Handle Demands
        cost = 0
        if order_type == "troops":
            cost = 15
            req_text = f"{value} воїнів"
            threat = "відібрання голосу (Mute) на добу!"
        else:
            cost = 30
            req_text = f"замок {value}"
            threat = "збільшення королівської данини та тавро бунтівника!"

        if king.authority < cost:
            return web.json_response({"error": f"Недостатньо авторитету! Потрібно {cost}."}, status=400)

        order_msg = (
            f"📜 <b>КОРОЛІВСЬКИЙ НАКАЗ</b>\n\n"
            f"Король <b>{king_name}</b> вимагає від <b>{target_name}</b> передати Короні <b>{req_text}</b>!\n\n"
            f"⚠️ Відмова означатиме <b>{threat}</b>"
        )
        
        try:
            king.authority -= cost
            await session.commit()
            await bot.send_message(CHAT_ID, order_msg, reply_markup=order_keyboard(target.user_id, order_type, value))
        except Exception as e:
            return web.json_response({"error": f"Помилка відправки в чат: {e}"}, status=500)

        return web.json_response({"message": f"✅ Наказ було відправлено у групу! Витрачено {cost} авторитету."})


@routes.post("/api/garrison")
async def api_garrison(request: web.Request) -> web.Response:
    """Manage garrison (add/remove troops)."""
    user_id = request["user_id"]
    data = await request.json()
    castle_id = data.get("castle_id")
    amount = data.get("amount") # positive to add, negative to remove

    if not castle_id or not amount:
        return web.json_response({"error": "Missing parameters"}, status=400)

    try:
        castle_id = int(castle_id)
        amount = int(amount)
    except ValueError:
        return web.json_response({"error": "Invalid parameters"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        castle = await session.get(Castle, castle_id)
        if not castle or castle.owner_id != user.user_id:
            return web.json_response({"error": "Це не ваш замок!"}, status=403)

        if amount > 0:
            # Adding to garrison
            if user.army_size < amount:
                return web.json_response({"error": "Недостатньо військ в армії!"}, status=400)
            user.army_size -= amount
            castle.garrison += amount
            msg = f"✅ {amount} воїнів додано до гарнізону!"
        else:
            # Removing from garrison
            remove_amount = abs(amount)
            if castle.garrison < remove_amount:
                return web.json_response({"error": "В гарнізоні немає стільки військ!"}, status=400)
            castle.garrison -= remove_amount
            user.army_size += remove_amount
            msg = f"✅ {remove_amount} воїнів повернуто в армію!"

        await session.commit()
        return web.json_response({"message": msg})


@routes.post("/api/punish")
async def api_punish(request: web.Request) -> web.Response:
    user_id = request["user_id"]
    bot = request.app['bot']
    try:
        data = await request.json()
        target_id = int(data.get("target_id"))
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)
        
    async with AsyncSessionLocal() as session:
        king = await get_user(session, user_id)
        if not king or king.role != "king":
            return web.json_response({"error": "Тільки Король може карати"}, status=400)
            
        target = await get_user(session, target_id)
        if not target:
            return web.json_response({"error": "Гравця не знайдено"}, status=404)
        if target.user_id == king.user_id:
            return web.json_response({"error": "Король не може покарати себе"}, status=400)
            
        if king.authority < 20:
            return web.json_response({"error": "Недостатньо авторитету! Потрібно 20."}, status=400)

        if target.king_tribute_rate >= 0.5:
            return web.json_response({"error": "Данина цього лорда вже досягла максимуму (50%)."}, status=400)
            
        king.authority -= 20
        target.king_tribute_rate = min(0.5, target.king_tribute_rate + 0.1)
        target.king_opinion = 'bad'
        await session.commit()
        
        from config.config import CHAT_ID
        target_name = f"@{target.username}" if target.username else target.first_name
        king_name = f"@{king.username}" if king.username else king.first_name
        punish_msg = f"⚖️ <b>КОРОЛІВСЬКА КАРА</b>\n\nКороль <b>{king_name}</b> наклав додаткові 10% данини на <b>{target_name}</b> за непокору! Тепер лорд віддає {int(target.king_tribute_rate * 100)}% доходу Короні."
        await bot.send_message(CHAT_ID, punish_msg)
        
        return web.json_response({"success": True, "message": f"Оподатковано +10%. Витрачено 20 авторитету."})

@routes.post("/api/mute")
async def api_mute(request: web.Request) -> web.Response:
    user_id = request["user_id"]
    bot = request.app['bot']
    try:
        data = await request.json()
        target_id = int(data.get("target_id"))
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)
        
    async with AsyncSessionLocal() as session:
        king = await get_user(session, user_id)
        if not king or king.role != "king":
            return web.json_response({"error": "Тільки Король може використовувати Mute!"}, status=403)
            
        if king.authority < 10:
            return web.json_response({"error": "Недостатньо авторитету! Потрібно 10."}, status=400)

        from bot.services.king import king_mute
        result_text = await king_mute(bot, session, user_id, target_id)
        
        from config.config import CHAT_ID
        if "не знайдено" not in result_text and "Тільки Король" not in result_text and "не може" not in result_text:
            king.authority -= 10
            await session.commit()
            await bot.send_message(CHAT_ID, result_text)
            return web.json_response({"success": True, "message": "Лорду зашито рота! Витрачено 10 авторитету."})
        else:
            return web.json_response({"error": result_text}, status=400)


@routes.post("/api/transfer")
async def api_transfer(request: web.Request) -> web.Response:
    user_id = request["user_id"]
    try:
        data = await request.json()
        target_id = int(data.get("target_id"))
        amount = int(data.get("amount", 0))
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)
        
    if amount <= 0:
        return web.json_response({"error": "Сума має бути більше нуля!"}, status=400)
        
    async with AsyncSessionLocal() as session:
        sender = await get_user(session, user_id)
        target = await get_user(session, target_id)
        
        if not sender or not target:
            return web.json_response({"error": "Гравця не знайдено!"}, status=404)
            
        if sender.alliance_id != target.alliance_id or not sender.alliance_id:
            return web.json_response({"error": "Ви можете надсилати війська лише членам свого альянсу!"}, status=400)
            
        if sender.army_size < amount:
            return web.json_response({"error": "Недостатньо військ!"}, status=400)
            
        target_cap = await get_army_cap(session, target.user_id)
        
        sender.army_size -= amount
        target.army_size = min(target.army_size + amount, target_cap)
        await session.commit()
        
        bot = request.app['bot']
        from config.config import CHAT_ID
        sender_name = f"@{sender.username}" if sender.username else sender.first_name
        target_name = f"@{target.username}" if target.username else target.first_name
        msg = f"🤝 <b>АЛЬЯНС</b>\n\n<b>{sender_name}</b> надіслав <b>{amount}</b> воїнів на допомогу <b>{target_name}</b>!"
        await bot.send_message(CHAT_ID, msg)
        
        return web.json_response({"success": True, "message": "Війська успішно надіслані!"})

@routes.post("/api/scout")
async def api_scout(request: web.Request) -> web.Response:
    user_id = request["user_id"]
    try:
        data = await request.json()
        castle_id = int(data.get("castle_id"))
        amount = int(data.get("amount", 0))
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)

    if amount < 10:
        return web.json_response({"error": "Мінімальний загін розвідників — 10 воїнів!"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        result = await session.execute(select(Castle).where(Castle.castle_id == castle_id))
        castle = result.scalar_one_or_none()
        
        if not user or not castle:
            return web.json_response({"error": "Не знайдено гравця або замок"}, status=404)
            
        if user.army_size < amount:
            return web.json_response({"error": "Недостатньо воїнів у вашій армії"}, status=400)
            
        user.army_size -= amount
        
        import random
        # Base chance: 50% + 1.5% per scout (so 10 scouts = 65% success, 30 scouts = 95%)
        chance = min(95.0, 50.0 + (amount * 1.5))
        # Detection chance: 15% base + 0.5% per scout
        detect_chance = min(50.0, 15.0 + (amount * 0.5))
        
        is_success = random.uniform(0, 100) <= chance
        is_detected = random.uniform(0, 100) <= detect_chance
        
        if is_detected and castle.owner_id and castle.owner_id != user.user_id:
            castle.garrison += amount
            await session.commit()
            return web.json_response({"error": f"Ваших розвідників виявили і захопили! Ви втратили {amount} воїнів.", "garrison": None}, status=400)
            
        if is_success:
            # Scouts return safely if successful
            user.army_size += amount
            from bot.models.db import ScoutReport
            from datetime import datetime
            
            report_result = await session.execute(select(ScoutReport).where(ScoutReport.user_id == user.user_id, ScoutReport.castle_id == castle.castle_id))
            report = report_result.scalar_one_or_none()
            if report:
                report.garrison = castle.garrison
                report.timestamp = datetime.utcnow()
            else:
                report = ScoutReport(user_id=user.user_id, castle_id=castle.castle_id, garrison=castle.garrison)
                session.add(report)
            await session.commit()
            return web.json_response({"success": True, "message": f"Розвідка успішна! Гарнізон замку: {castle.garrison}", "garrison": castle.garrison})
        else:
            await session.commit()
            return web.json_response({"error": f"Розвідникам не вдалося дізнатися точне число. Вони не повернулися.", "garrison": None}, status=400)

@routes.post("/api/alliance/create")
async def api_alliance_create(request: web.Request) -> web.Response:
    """Create a new alliance."""
    user_id = request["user_id"]
    try:
        data = await request.json()
        alliance_name = str(data.get("name", "")).strip()
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)

    if not alliance_name or len(alliance_name) > 30:
        return web.json_response({"error": "Назва альянсу має містити від 1 до 30 символів."}, status=400)

    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            return web.json_response({"error": "Користувача не знайдено"}, status=404)

        if user.alliance_id:
            return web.json_response({"error": "Ви вже перебуваєте в альянсі!"}, status=400)

        # Check if alliance name is taken
        from bot.models.db import Alliance
        from sqlalchemy import select
        existing = await session.execute(select(Alliance).where(Alliance.name == alliance_name))
        if existing.scalar_one_or_none():
            return web.json_response({"error": f"Альянс з назвою '{alliance_name}' вже існує!"}, status=400)

        alliance = Alliance(
            name=alliance_name,
            leader_id=user.user_id,
        )
        session.add(alliance)
        await session.flush()

        user.alliance_id = alliance.alliance_id
        await session.commit()

        return web.json_response({"success": True, "message": f"Альянс «{alliance_name}» успішно створено!"})

@routes.post("/api/alliance/invite")
async def api_alliance_invite(request: web.Request) -> web.Response:
    """Invite a user to the alliance via WebApp."""
    user_id = request["user_id"]
    try:
        data = await request.json()
        target_id = int(data.get("target_id", 0))
    except Exception:
        return web.json_response({"error": "Invalid data"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user or not user.alliance_id:
            return web.json_response({"error": "Ви не в альянсі!"}, status=400)

        from bot.models.db import Alliance
        alliance = await session.get(Alliance, user.alliance_id)
        if not alliance or alliance.leader_id != user.user_id:
            return web.json_response({"error": "Лише Глава може запрошувати!"}, status=400)

        target = await get_user(session, target_id)
        if not target:
            return web.json_response({"error": "Гравця не знайдено."}, status=404)
        if target.user_id == user.user_id:
            return web.json_response({"error": "Ви не можете запросити себе!"}, status=400)
        if target.alliance_id:
            return web.json_response({"error": "Цей гравець вже у якомусь альянсі!"}, status=400)

        bot = request.app['bot']
        invite_text = (
            f"📯 <b>Запрошення до Коаліції!</b>\n\n"
            f"Глава <b>@{user.username or user.first_name}</b> "
            f"запрошує вас до коаліції «<b>{alliance.name}</b>».\n\n"
            f"Оберіть свою долю, Лорде:"
        )

        from bot.handlers.alliance import alliance_invite_keyboard
        try:
            await bot.send_message(
                chat_id=target.user_id,
                text=invite_text,
                reply_markup=alliance_invite_keyboard(alliance.alliance_id),
            )
            return web.json_response({"success": True, "message": f"Запрошення надіслано!"})
        except Exception:
            return web.json_response({"error": "Не вдалося надіслати запрошення."}, status=400)

@routes.post("/api/alliance/leave")
async def api_alliance_leave(request: web.Request) -> web.Response:
    """Leave or disband the alliance via WebApp."""
    user_id = request["user_id"]
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user or not user.alliance_id:
            return web.json_response({"error": "Ви не в альянсі!"}, status=400)

        from bot.models.db import Alliance, User
        from sqlalchemy import select
        alliance = await session.get(Alliance, user.alliance_id)
        if not alliance:
            user.alliance_id = None
            await session.commit()
            return web.json_response({"success": True, "message": "Ви більше не в альянсі."})

        is_leader = alliance.leader_id == user.user_id
        if is_leader:
            result = await session.execute(select(User).where(User.alliance_id == alliance.alliance_id))
            members = result.scalars().all()
            for member in members:
                member.alliance_id = None
            await session.delete(alliance)
            await session.commit()
            return web.json_response({"success": True, "message": "Альянс успішно розформовано!"})
        else:
            user.alliance_id = None
            await session.commit()
            return web.json_response({"success": True, "message": "Ви покинули альянс!"})



def setup_api(bot) -> web.Application:
    """Initialize aiohttp application."""
    app = web.Application(middlewares=[auth_middleware])
    app['bot'] = bot
    app.add_routes(routes)
    
    # CORS setup could go here if needed, but since it's served on same origin it's fine
    
    # Serve static files from webapp/dist directory
    if webapp_dir.exists():
        if (webapp_dir / "assets").exists():
            app.router.add_static("/assets", webapp_dir / "assets")
        
        # Serve index.html for the root path
        async def index_handler(request: web.Request) -> web.Response:
            return web.FileResponse(webapp_dir / "index.html")
            
        app.router.add_get("/", index_handler)
        
        # Fallback for all other routes to return index.html (for client-side routing)
        # Note: In a real app we'd add static routes for other files in dist. 
        # Here we add a catch-all route.
        async def fallback_handler(request: web.Request) -> web.Response:
            path = webapp_dir / request.match_info['path']
            if path.exists() and path.is_file():
                return web.FileResponse(path)
            return web.FileResponse(webapp_dir / "index.html")
            
        app.router.add_get("/{path:.*}", fallback_handler)
        
    return app
