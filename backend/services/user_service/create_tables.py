"""
Скрипт для создания таблиц в базе данных
"""
import asyncio
from database.models import Base
from database.database import engine

async def create_tables():
    """Создание таблиц в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Таблицы успешно созданы!")

if __name__ == "__main__":
    asyncio.run(create_tables()) 