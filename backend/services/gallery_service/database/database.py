import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Конфигурация базы данных
DB_USER = os.getenv("DB_USER", "MikleSibFish")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Mishatrof1!?")
DB_HOST = os.getenv("DB_GALLERY_HOST", "db_gallery")
DB_PORT = os.getenv("DB_GALLERY_PORT", "5432")
DB_NAME = os.getenv("DB_GALLERY_NAME", "db_gallery")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создание движка базы данных
engine = create_async_engine(DATABASE_URL, echo=True)

# Создание сессии
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 