from fastapi import Depends, HTTPException, Path, status

from database.database import get_db
from database.models import Category, Post, Topic
from src.utils.auth import User, get_current_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



async def get_category_or_404(
    category_id: int = Path(...),
    db: AsyncSession = Depends(get_db)
) -> Category:
    """Получение категории по ID или 404"""
    query = select(Category).where(Category.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Категория с ID {category_id} не найдена"
        )
    
    return category

async def get_topic_or_404(
    topic_id: int = Path(...),
    db: AsyncSession = Depends(get_db)
) -> Topic:
    """Получение темы по ID или 404"""
    query = select(Topic).where(
        Topic.id == topic_id,
        Topic.is_deleted == False
    )
    result = await db.execute(query)
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Тема с ID {topic_id} не найдена"
        )
    
    return topic

async def get_post_or_404(
    post_id: int = Path(...),
    db: AsyncSession = Depends(get_db)
) -> Post:
    """Получение сообщения по ID или 404"""
    query = select(Post).where(
        Post.id == post_id,
        Post.is_deleted == False
    )
    result = await db.execute(query)
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сообщение с ID {post_id} не найдено"
        )
    
    return post

async def check_topic_owner_or_moderator(
    topic: Topic = Depends(get_topic_or_404),
    current_user: User = Depends(get_current_user)
) -> Topic:
    """Проверка, что пользователь является владельцем темы или модератором"""
    if topic.author_id != current_user.id and not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этой операции"
        )
    return topic

async def check_post_owner_or_moderator(
    post: Post = Depends(get_post_or_404),
    current_user: User = Depends(get_current_user)
) -> Post:
    """Проверка, что пользователь является владельцем сообщения или модератором"""
    if post.author_id != current_user.id and not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этой операции"
        )
    return post

def check_is_moderator(current_user: User = Depends(get_current_user)) -> User:
    """Проверка, что пользователь является модератором или администратором"""
    if not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права модератора"
        )
    return current_user

def check_is_admin(current_user: User = Depends(get_current_user)) -> User:
    """Проверка, что пользователь является администратором"""
    logger.info(f"Проверка прав администратора для пользователя {current_user.id}")
    if not current_user.is_admin:
        logger.warning(f"Пользователь {current_user.id} не имеет прав администратора")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    logger.info(f"Пользователь {current_user.id} успешно прошел проверку прав администратора")
    return current_user