import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from bot.models.db import AsyncSessionLocal, Castle
from sqlalchemy import select, update, delete

RENAME_MAP = {
    "Вінтерфелл": "Північ",
    "Ріверран": "Річкові Землі",
    "Орлине Гніздо": "Долина Аррен",
    "Кастерлі Рок": "Західні Землі",
    "Королівська Гавань": "Королівські Землі",
    "Хайгарден": "Простір",
    "Штормовий Кінець": "Штормові Землі",
    "Сонячний Спис": "Дорн"
}

from bot.models.db import CASTLE_NAMES

async def main():
    async with AsyncSessionLocal() as session:
        for old_name, new_name in RENAME_MAP.items():
            await session.execute(
                update(Castle).where(Castle.name == old_name).values(name=new_name)
            )
        # Delete any castles that are not in the new 10-item list
        await session.execute(
            delete(Castle).where(Castle.name.not_in(CASTLE_NAMES))
        )
        await session.commit()
        print("Database updated!")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
