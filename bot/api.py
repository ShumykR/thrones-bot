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
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from bot.models.db import AsyncSessionLocal, User, Castle, get_user
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
    if request.path.startswith("/api/"):
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
            "independence_points": user.independence_points,
            "castles_count": len(castles),
            "castles": [{"id": c.castle_id, "name": c.name} for c in castles],
        })


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
            
        return web.json_response({
            "king": {"id": king.user_id, "name": king.first_name} if king else None,
            "castles": castles_data,
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
            # Create a temporary empty defender if there's no owner? 
            # Or fail? The logic says "Замок не належить лорду".
            # Actually, attacking free castles is allowed in WebApp if we have an owner check bypass.
            # But the current DB logic in war.py requires a defender. 
            # Let's see how war.py handles free castles.
            return web.json_response({"error": "Цей замок нічийний! У ньому має бути хоч якийсь власник, щоб атакувати."}, status=400)
            
        defender = await session.get(User, target_castle.owner_id)
        if not defender:
            return web.json_response({"error": "Власника не знайдено"}, status=404)

        if attacker.role == "puppet" and attacker.master_id == defender.user_id:
            return web.json_response({"error": "Ви не можете атакувати свого Власника!"}, status=400)

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
            logger.exception("Failed to send battle announcement from WebApp")

        await session.commit()

        from bot.services.battle import run_battle_task
        import asyncio
        asyncio.create_task(run_battle_task(battle.battle_id, bot))

        return web.json_response({"success": True, "message": "Війська вирушили на штурм!"})


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
