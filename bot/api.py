"""
ThroneChat — WebApp API
REST API for the Telegram Mini App using aiohttp.
"""

import hashlib
import hmac
import json
import logging
import urllib.parse
from pathlib import Path

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from bot.models.db import AsyncSessionLocal, User, Castle, get_user
from config.config import BOT_TOKEN, MIN_ATTACK_ARMY

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()
webapp_dir = Path(__file__).resolve().parent.parent / "webapp"


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


def setup_api() -> web.Application:
    """Initialize aiohttp application."""
    app = web.Application(middlewares=[auth_middleware])
    app.add_routes(routes)
    
    # CORS setup could go here if needed, but since it's served on same origin it's fine
    
    # Serve static files from webapp directory
    if webapp_dir.exists():
        if (webapp_dir / "assets").exists():
            app.router.add_static("/assets", webapp_dir / "assets")
        if (webapp_dir / "screens").exists():
            app.router.add_static("/screens", webapp_dir / "screens")
        
        # Serve index.html for the root path
        async def index_handler(request: web.Request) -> web.Response:
            return web.FileResponse(webapp_dir / "index.html")
            
        app.router.add_get("/", index_handler)
        app.router.add_static("/", webapp_dir)
        
    return app
