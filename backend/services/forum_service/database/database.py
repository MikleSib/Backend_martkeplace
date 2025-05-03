from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings

# Создаем асинхронный движок SQLAlchemy для работы с базой данных
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True,
)

# Создаем фабрику сессий
async_session_factory = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Функция-генератор для получения сессии базы данных
    Используется как Dependency в FastAPI для инъекции сессии БД в эндпоинты
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close() 