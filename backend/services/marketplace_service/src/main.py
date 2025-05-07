from fastapi import FastAPI
from .endpoints import router
from database import engine, Base, create_tables, seed_sample_data, get_db
import os

app = FastAPI(title="Marketplace Service", 
              description="API для работы с товарами маркетплейсов",
              version="0.1.0")

app.include_router(router)

@app.on_event("startup")
async def startup():
    """
    Инициализация приложения при запуске.
    Создает таблицы в базе данных и добавляет тестовые данные, если указан флаг FORCE_DB_RECREATE
    """
    force_recreate = os.environ.get("FORCE_DB_RECREATE", "false").lower() == "true"
    
    if force_recreate:
        # Пересоздаем все таблицы при старте
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        
        # Добавляем тестовые данные
        async for db in get_db():
            await seed_sample_data(db)
            break
    else:
        # Просто создаем таблицы, если они не существуют
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health_check():
    """
    Проверка работоспособности сервиса
    """
    return {"status": "healthy"} 