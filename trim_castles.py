import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from bot.models.db import AsyncSessionLocal, Castle
from sqlalchemy import select, delete

async def main():
    async with AsyncSessionLocal() as session:
        # Get castles to keep
        from bot.models.db import CASTLE_NAMES
        print(f"Keeping {len(CASTLE_NAMES)} castles: {CASTLE_NAMES}")
        
        # Delete extra castles
        await session.execute(delete(Castle).where(Castle.name.not_in(CASTLE_NAMES)))
        await session.commit()
        print("Extra castles deleted.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
