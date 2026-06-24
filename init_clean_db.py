import sys
import os
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from bot.models.db import init_db, AsyncSessionLocal, Castle

async def main():
    # 1. Initialize the database (creates tables)
    print("Ініціалізація чистої бази даних...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        
        # Очищуємо всі поточні землі
        await session.execute(delete(Castle))
        
        # 1.5 Створення 10 вільних земель
        lands_data = [
            (1, "Землі за Стіною", 10),
            (2, "Північ", 20),
            (3, "Західні Землі", 25),
            (4, "Залізні Острови", 10),
            (5, "Долина Аррен", 20),
            (6, "Королівські Землі", 30),
            (7, "Дорн", 15),
            (8, "Простір", 25),
            (9, "Штормові Землі", 20),
            (10, "Річкові Землі", 15)
        ]

        for c_id, name, aph in lands_data:
            # Замки не мають власника і гарнізону (вільні для захоплення або для Короля)
            session.add(Castle(castle_id=c_id, name=name, army_per_hour=aph, garrison=0))
        
        await session.commit()
        print("Землі успішно створено. Усі користувачі відсутні.")

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
