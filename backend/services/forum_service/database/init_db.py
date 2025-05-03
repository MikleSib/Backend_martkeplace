import asyncio
import logging
import os
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from config.settings import settings
from database.database import get_db
from database.models import Base, Category

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=True,
    future=True
)

# Создаем фабрику сессий
async_session_factory = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)

# Инициализация начальных данных
async def init_db():
    # Проверяем наличие переменной среды для принудительного пересоздания таблиц
    force_recreate = os.getenv("FORCE_DB_RECREATE", "").lower() in ["true", "1", "yes"]
    
    async with engine.begin() as conn:
        # Проверяем существование таблиц
        try:
            # Пробуем получить список категорий
            async with async_session_factory() as session:
                query = select(Category)
                result = await session.execute(query)
                categories = result.scalars().all()
                
                # Если категории уже есть и не требуется пересоздание, выходим
                if categories and not force_recreate:
                    logger.info("База данных уже инициализирована")
                    return
        except Exception as e:
            logger.info(f"Таблицы не существуют или ошибка доступа: {e}")
            
        # Создаем таблицы
        logger.info("Создание таблиц базы данных")
        if force_recreate:
            logger.warning("Принудительное пересоздание таблиц (FORCE_DB_RECREATE=True)")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем начальные категории
    async with async_session_factory() as session:
        try:
            # Проверяем, есть ли уже категории
            query = select(Category)
            result = await session.execute(query)
            existing_categories = result.scalars().all()
            
            if existing_categories:
                logger.info(f"В базе данных уже есть {len(existing_categories)} категорий")
                return
                
            # Основные категории
            main_categories = [
                Category(
                    title="Рыболовные снасти",
                    description="Обсуждение удочек, катушек, лесок и других снастей",
                    order=1
                ),
                Category(
                    title="Методы ловли",
                    description="Техники и методы ловли рыбы",
                    order=2
                ),
                Category(
                    title="Водоемы и места ловли",
                    description="Обсуждение рыболовных мест и водоемов",
                    order=3
                ),
                Category(
                    title="Виды рыб",
                    description="Обсуждение различных видов рыб и их ловли",
                    order=4
                ),
                Category(
                    title="Рыболовные соревнования",
                    description="Информация о соревнованиях и турнирах",
                    order=5
                ),
                Category(
                    title="Общие вопросы",
                    description="Любые вопросы, не попадающие в другие категории",
                    order=6
                ),
            ]
            
            session.add_all(main_categories)
            await session.commit()
            
            # Получаем созданные категории для добавления подкатегорий
            for category in main_categories:
                await session.refresh(category)
            
            # Подкатегории для "Рыболовные снасти"
            snasti_subcategories = [
                Category(
                    title="Удилища",
                    description="Обсуждение удилищ всех типов",
                    parent_id=main_categories[0].id,
                    order=1
                ),
                Category(
                    title="Катушки",
                    description="Спиннинговые, безынерционные и другие катушки",
                    parent_id=main_categories[0].id,
                    order=2
                ),
                Category(
                    title="Приманки",
                    description="Воблеры, блесны, силикон и другие приманки",
                    parent_id=main_categories[0].id,
                    order=3
                ),
                Category(
                    title="Оснастки",
                    description="Монтажи, лески, шнуры и другие оснастки",
                    parent_id=main_categories[0].id,
                    order=4
                ),
            ]
            
            # Подкатегории для "Методы ловли"
            metody_subcategories = [
                Category(
                    title="Спиннинг",
                    description="Ловля на спиннинг",
                    parent_id=main_categories[1].id,
                    order=1
                ),
                Category(
                    title="Фидер",
                    description="Фидерная ловля",
                    parent_id=main_categories[1].id,
                    order=2
                ),
                Category(
                    title="Поплавочная ловля",
                    description="Ловля на поплавочную удочку",
                    parent_id=main_categories[1].id,
                    order=3
                ),
                Category(
                    title="Нахлыст",
                    description="Нахлыстовая ловля",
                    parent_id=main_categories[1].id,
                    order=4
                ),
                Category(
                    title="Зимняя рыбалка",
                    description="Ловля со льда",
                    parent_id=main_categories[1].id,
                    order=5
                ),
            ]
            
            # Добавляем подкатегории
            session.add_all(snasti_subcategories)
            session.add_all(metody_subcategories)
            await session.commit()
            
            logger.info("Начальные данные успешно добавлены в базу данных")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise

# Для запуска инициализации вручную
if __name__ == "__main__":
    asyncio.run(init_db()) 