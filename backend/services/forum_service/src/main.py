from fastapi import FastAPI, Request, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging
from typing import List
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from config.settings import settings
from src.routers import categories, topics, posts
from src.schemas.common import HealthResponse
from src.schemas.topic import TopicResponse
from database.init_db import init_db
from database.database import get_db
from database.models import Topic

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем приложение FastAPI
app = FastAPI(
    title="Forum Service API",
    description="API для форумного сервиса",
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене следует заменить на список доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Внутренняя ошибка сервера: {str(exc)}"}
    )

# Событие запуска приложения для инициализации базы данных
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Запуск инициализации базы данных...")
        await init_db()
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")

# Корневой эндпоинт
@app.get("/")
async def root():
    return {"message": "Добро пожаловать в API форума рыболовов"}

# Роуты для проверки здоровья сервиса
@app.get("/health")
async def health_check():
    """Проверка доступности сервиса"""
    return {"status": "ok", "service": settings.SERVICE_NAME, "version": settings.VERSION}

# Отдельный маршрут для получения самых активных тем форума
@app.get("/api/v1/active-topics", response_model=List[TopicResponse])
async def get_active_forum_topics(
    limit: int = Query(5, description="Количество тем для получения"),
    db: AsyncSession = Depends(get_db)
):
    """Получение тем с наибольшим количеством сообщений из любых категорий"""
    try:
        # Запрос для получения тем с наибольшим количеством сообщений
        query = select(Topic).where(Topic.is_deleted == False).order_by(desc(Topic.posts_count)).limit(limit)
        
        result = await db.execute(query)
        topics = result.scalars().all()
        
        # Получаем информацию о пользователях
        user_ids = set(topic.author_id for topic in topics)
        user_ids.update(topic.last_post_author_id for topic in topics if topic.last_post_author_id)
        
        users_by_id = {}
        if user_ids:
            try:
                async with httpx.AsyncClient() as client:
                    # Получаем данные пользователей по одному используя проверенный эндпоинт
                    for user_id in user_ids:
                        try:
                            user_response = await client.get(f"{settings.USER_SERVICE_URL}/users/{user_id}")
                            logger.info(f"User service response for user {user_id}: {user_response.status_code}")
                            if user_response.status_code == 200:
                                user = user_response.json()
                                users_by_id[user["user_id"]] = user
                        except Exception as e:
                            logger.error(f"Ошибка при получении данных пользователя {user_id}: {str(e)}")
            except httpx.RequestError as e:
                # В случае ошибки продолжаем без данных пользователей
                logger.error(f"Ошибка при запросе к сервису пользователей: {str(e)}")
                pass
        
        # Формируем ответ с данными пользователей
        result_topics = []
        for topic in topics:
            topic_data = dict(topic.__dict__)
            
            # Добавляем данные автора
            if topic.author_id in users_by_id:
                author = users_by_id[topic.author_id]
                topic_data["author_username"] = author.get("username", "Неизвестный")
                topic_data["author_fullname"] = author.get("full_name", "")
                topic_data["author_avatar"] = author.get("avatar")
            else:
                topic_data["author_username"] = "Неизвестный"
                topic_data["author_fullname"] = ""
                topic_data["author_avatar"] = None
            
            # Добавляем данные автора последнего сообщения
            if topic.last_post_author_id and topic.last_post_author_id in users_by_id:
                last_author = users_by_id[topic.last_post_author_id]
                topic_data["last_post_author_username"] = last_author.get("username", "Неизвестный")
                topic_data["last_post_author_avatar"] = last_author.get("avatar")
            elif topic.last_post_author_id:
                topic_data["last_post_author_username"] = "Неизвестный"
                topic_data["last_post_author_avatar"] = None
            
            result_topics.append(topic_data)
        
        return result_topics
    except Exception as e:
        logger.error(f"Ошибка при получении активных тем: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении активных тем: {str(e)}")

# Регистрируем роутеры
app.include_router(categories.router, prefix=settings.API_PREFIX)
app.include_router(topics.router, prefix=settings.API_PREFIX)
app.include_router(posts.router, prefix=settings.API_PREFIX)

# Для запуска сервиса напрямую через Python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8009, reload=True) 