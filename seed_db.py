import sys
import os
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from bot.models.db import init_db, AsyncSessionLocal, User, Castle
from sqlalchemy import select

async def main():
    # 1. Initialize the database (creates tables)
    print("Ініціалізація бази даних...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        
        # Очищуємо всі поточні землі, щоб перезаписати з конкретними ID
        await session.execute(delete(Castle))
        
        # 1.5 Створення 10 земель з фіксованими ID (щоб ви могли відкоригувати їх для мапи)
        # Формат: (ID, "Назва Землі")
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
            session.add(Castle(castle_id=c_id, name=name, army_per_hour=aph))
        
        await session.commit()
        print("Землі успішно створено з вказаними ID.")
    
    async with AsyncSessionLocal() as session:
        # Check if users already exist
        result = await session.execute(select(User))
        existing_users = result.scalars().all()
        
        # Mock users data with Game of Thrones characters
        mock_users_data = [
            {"user_id": 111111111, "username": "jon_snow", "first_name": "Джон Сноу", "role": "king", "army_size": 1200, "authority": 50, "king_tribute_rate": 0.0},
            {"user_id": 222222222, "username": "jaime_lannister", "first_name": "Джейме Ланністер", "role": "lord", "army_size": 800, "authority": 0, "king_tribute_rate": 0.0},
            {"user_id": 333333333, "username": "daenerys_targaryen", "first_name": "Данерис Таргарієн", "role": "lord", "army_size": 1500, "authority": 0, "king_tribute_rate": 0.0},
            {"user_id": 444444444, "username": "stannis_baratheon", "first_name": "Станніс Баратеон", "role": "lord", "army_size": 600, "authority": 0, "king_tribute_rate": 0.1},
        ]
        
        users_dict = {}
        
        print("\nПеревірка та створення користувачів...")
        for data in mock_users_data:
            result = await session.execute(select(User).where(User.user_id == data["user_id"]))
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    user_id=data["user_id"],
                    username=data["username"],
                    first_name=data["first_name"],
                    role=data["role"],
                    army_size=data["army_size"],
                    authority=data["authority"],
                    king_tribute_rate=data["king_tribute_rate"]
                )
                session.add(user)
                print(f"Створено користувача: {user.first_name} (@{user.username})")
            else:
                user.role = data["role"]
                user.army_size = data["army_size"]
                user.first_name = data["first_name"]
                user.username = data["username"]
                user.authority = data["authority"]
                user.king_tribute_rate = data["king_tribute_rate"]
                print(f"Користувач {user.first_name} вже існує. Оновлено.")
            users_dict[data["username"]] = user

        await session.commit()

        # Let's assign some castles
        print("\nПризначення замків для користувачів...")
        result = await session.execute(select(Castle))
        castles = result.scalars().all()
        
        # Map castles by name
        castle_map = {c.name: c for c in castles}
        
        # Mapping of username -> list of castle names to assign
        assignments = {
            "jon_snow": ["Північ"],
            "jaime_lannister": ["Західні Землі", "Простір"],
            "daenerys_targaryen": ["Драконячий Камінь"],
            "stannis_baratheon": ["Штормові Землі"],
        }
        
        for username, castle_names in assignments.items():
            user = users_dict[username]
            for c_name in castle_names:
                if c_name in castle_map:
                    castle = castle_map[c_name]
                    castle.owner_id = user.user_id
                    castle.garrison = 200  # Set garrison
                    print(f"Замок '{c_name}' призначено для {user.first_name}")
                else:
                    print(f"Увага: Замок '{c_name}' не знайдено в базі даних!")
                    
        await session.commit()
        print("\nБазу даних успішно заповнено!")
        
        # Output current state
        print("\n--- Поточний стан бази даних ---")
        for username, user in users_dict.items():
            await session.refresh(user)
            result = await session.execute(select(Castle).where(Castle.owner_id == user.user_id))
            user_castles = result.scalars().all()
            castle_list = ", ".join([c.name for c in user_castles]) if user_castles else "Немає"
            print(f"Лорд: {user.first_name} (@{user.username}) | Роль: {user.role} | Армія: {user.army_size} | Замки: {castle_list}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
