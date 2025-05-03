from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from config.settings import settings
from database.database import get_db
from database.models import Category, Post, Topic
from src.schemas.common import PaginatedResponse
from src.schemas.post import PostCreate
from src.schemas.topic import (TopicCreate, TopicDetailResponse, TopicResponse,
                             TopicUpdate)
from src.utils.auth import User, get_current_user
from src.utils.dependencies import (check_is_moderator, get_category_or_404,
                                 get_topic_or_404, check_topic_owner_or_moderator)
from src.utils.pagination import paginate

router = APIRouter(prefix="/topics", tags=["topics"])

@router.get("", response_model=PaginatedResponse[TopicResponse])
async def get_topics(
    category_id: Optional[int] = Query(None, description="ID категории для фильтрации"),
    author_id: Optional[int] = Query(None, description="ID автора для фильтрации"),
    pinned: Optional[bool] = Query(None, description="Фильтр закрепленных тем"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка тем с пагинацией и фильтрацией"""
    # Базовый запрос
    query = select(Topic).where(Topic.is_deleted == False)
    
    # Применяем фильтры
    if category_id:
        query = query.where(Topic.category_id == category_id)
    
    if author_id:
        query = query.where(Topic.author_id == author_id)
    
    if pinned is not None:
        query = query.where(Topic.is_pinned == pinned)
    
    # Сортировка: сначала закрепленные, потом по дате последнего сообщения
    query = query.order_by(desc(Topic.is_pinned), desc(Topic.last_post_date))
    
    # Пагинация результатов
    pagination_result = await paginate(db, query, page, page_size)
    
    # Получаем информацию о пользователях
    topics = pagination_result["items"]
    
    # Загружаем данные пользователей из user_service
    user_ids = set(topic.author_id for topic in topics)
    user_ids.update(topic.last_post_author_id for topic in topics if topic.last_post_author_id)
    
    users_by_id = {}
    if user_ids:
        try:
            async with httpx.AsyncClient() as client:
                # Пробуем получить пользователей по одному через проверенный эндпоинт
                for user_id in user_ids:
                    try:
                        user_response = await client.get(f"{settings.USER_SERVICE_URL}/users/{user_id}")
                        if user_response.status_code == 200:
                            user = user_response.json()
                            users_by_id[user["id"]] = user
                    except Exception:
                        pass
        except httpx.RequestError:
            # В случае ошибки продолжаем без данных пользователей
            pass
    
    # Обогащаем темы информацией о пользователях
    for topic in topics:
        # Добавляем данные автора темы
        if topic.author_id in users_by_id:
            author = users_by_id[topic.author_id]
            topic.author_username = author.get("username", "Неизвестный")
            topic.author_avatar = author.get("avatar")
            topic.author_fullname = author.get("full_name", "")
        else:
            topic.author_username = "Неизвестный"
            topic.author_avatar = None
            topic.author_fullname = ""
        
        # Добавляем данные автора последнего сообщения
        if topic.last_post_author_id and topic.last_post_author_id in users_by_id:
            last_author = users_by_id[topic.last_post_author_id]
            topic.last_post_author_username = last_author.get("username", "Неизвестный")
            topic.last_post_author_avatar = last_author.get("avatar")
            topic.last_post_author_fullname = last_author.get("full_name", "")
        elif topic.last_post_author_id:
            topic.last_post_author_username = "Неизвестный"
            topic.last_post_author_avatar = None
            topic.last_post_author_fullname = ""
    
    # Формируем ответ
    return PaginatedResponse[TopicResponse](
        items=topics,
        total=pagination_result["total"],
        page=pagination_result["page"],
        page_size=pagination_result["page_size"],
        pages=pagination_result["pages"]
    )

@router.get("/{topic_id}", response_model=TopicDetailResponse)
async def get_topic_detail(
    topic: Topic = Depends(get_topic_or_404),
    db: AsyncSession = Depends(get_db)
):
    """Получение детальной информации о теме"""
    # Увеличиваем счетчик просмотров
    await db.execute(
        update(Topic)
        .where(Topic.id == topic.id)
        .values(views_count=Topic.views_count + 1)
    )
    await db.commit()
    
    # Получаем данные категории
    category_query = select(Category).where(Category.id == topic.category_id)
    category = await db.scalar(category_query)
    
    # Получаем данные автора из user_service
    author_data = {"username": "Неизвестный", "avatar": None}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.USER_SERVICE_URL}/users/{topic.author_id}"
            )
            if response.status_code == 200:
                user = response.json()
                author_data = {
                    "username": user.get("username", "Неизвестный"),
                    "avatar": user.get("avatar")
                }
    except httpx.RequestError:
        # В случае ошибки используем дефолтные данные
        pass
    
    # Формируем ответ
    result = dict(topic.__dict__)
    result["author_username"] = author_data["username"]
    result["author_avatar"] = author_data["avatar"]
    result["category_title"] = category.title if category else "Неизвестная категория"
    
    return result

@router.post("", response_model=TopicDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    topic_data: TopicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создание новой темы с первым сообщением"""
    # Проверяем существование категории
    category_query = select(Category).where(Category.id == topic_data.category_id)
    category = await db.scalar(category_query)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Категория с ID {topic_data.category_id} не найдена"
        )
    
    # Создаем новую тему
    new_topic = Topic(
        title=topic_data.title,
        category_id=topic_data.category_id,
        author_id=current_user.id,
        tags=topic_data.tags,
        created_at=datetime.utcnow(),
        last_post_author_id=current_user.id,
        last_post_date=datetime.utcnow()
    )
    db.add(new_topic)
    await db.flush()  # Получаем ID темы
    
    # Создаем первое сообщение
    first_post = Post(
        topic_id=new_topic.id,
        author_id=current_user.id,
        content=topic_data.content,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        is_topic_starter=True
    )
    db.add(first_post)
    await db.flush()
    
    # Обновляем тему с данными о первом сообщении
    new_topic.last_post_id = first_post.id
    new_topic.posts_count = 1
    
    # Обновляем счетчики в категории
    category.topics_count += 1
    category.messages_count += 1
    
    await db.commit()
    await db.refresh(new_topic)
    
    # Формируем ответ
    result = dict(new_topic.__dict__)
    result["author_username"] = current_user.username
    result["author_avatar"] = None  # В идеале получить из user_service
    result["category_title"] = category.title
    
    return result

@router.put("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_data: TopicUpdate,
    topic: Topic = Depends(check_topic_owner_or_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Обновление темы (владельцем или модератором)"""
    # Если меняется категория, проверяем ее существование
    if topic_data.category_id is not None and topic_data.category_id != topic.category_id:
        category_query = select(Category).where(Category.id == topic_data.category_id)
        category = await db.scalar(category_query)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Категория с ID {topic_data.category_id} не найдена"
            )
        
        # Обновляем счетчики в категориях
        old_category_query = select(Category).where(Category.id == topic.category_id)
        old_category = await db.scalar(old_category_query)
        if old_category:
            old_category.topics_count = max(0, old_category.topics_count - 1)
            old_category.messages_count = max(0, old_category.messages_count - topic.posts_count)
        
        category.topics_count += 1
        category.messages_count += topic.posts_count
    
    # Обновляем данные темы
    update_data = topic_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(topic, key, value)
    
    await db.commit()
    await db.refresh(topic)
    
    return topic

@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic: Topic = Depends(check_topic_owner_or_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Удаление темы (владельцем или модератором)"""
    # Логическое удаление темы
    topic.is_deleted = True
    
    # Обновляем счетчики в категории
    category_query = select(Category).where(Category.id == topic.category_id)
    category = await db.scalar(category_query)
    if category:
        category.topics_count = max(0, category.topics_count - 1)
        category.messages_count = max(0, category.messages_count - topic.posts_count)
    
    await db.commit()
    
    return None

@router.put("/{topic_id}/pin", response_model=TopicResponse)
async def pin_topic(
    topic: Topic = Depends(get_topic_or_404),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(check_is_moderator)
):
    """Закрепление/открепление темы (только для модераторов)"""
    topic.is_pinned = not topic.is_pinned
    await db.commit()
    await db.refresh(topic)
    
    return topic

@router.put("/{topic_id}/close", response_model=TopicResponse)
async def close_topic(
    topic: Topic = Depends(get_topic_or_404),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(check_is_moderator)
):
    """Закрытие/открытие темы (только для модераторов)"""
    topic.is_closed = not topic.is_closed
    await db.commit()
    await db.refresh(topic)
    
    return topic 