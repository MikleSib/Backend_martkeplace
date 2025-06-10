from datetime import datetime
from typing import List
import math
import httpx
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db
from database.models import Gallery, GalleryComment
from src.schemas.comment import (
    CommentCreate, CommentUpdate, CommentResponse, 
    CommentsPaginatedResponse, MessageResponse
)
from src.schemas.gallery import UserInfo
from src.utils.auth import User, get_current_user

router = APIRouter(prefix="/galleries", tags=["comments"])

# URL сервисов
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user_service:8000/api/v1")

async def get_user_info(user_id: int) -> UserInfo:
    """Получение информации о пользователе из user_service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}")
            if response.status_code == 200:
                user_data = response.json()
                return UserInfo(
                    id=user_data["user_id"],
                    username=user_data.get("username", "Неизвестный"),
                    fullname=user_data.get("full_name"),
                    avatar=user_data.get("avatar"),
                    registration_date=user_data.get("registration_date"),
                    posts_count=user_data.get("posts_count", 0),
                    role=user_data.get("role", "user")
                )
    except httpx.RequestError:
        pass
    return None

async def get_users_batch(user_ids: List[int]) -> dict:
    """Получение информации о нескольких пользователях"""
    users_by_id = {}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{USER_SERVICE_URL}/users/batch",
                json={"user_ids": user_ids}
            )
            if response.status_code == 200:
                users_data = response.json()
                for user_data in users_data:
                    users_by_id[user_data["user_id"]] = UserInfo(
                        id=user_data["user_id"],
                        username=user_data.get("username", "Неизвестный"),
                        fullname=user_data.get("full_name"),
                        avatar=user_data.get("avatar"),
                        registration_date=user_data.get("registration_date"),
                        posts_count=user_data.get("posts_count", 0),
                        role=user_data.get("role", "user")
                    )
    except httpx.RequestError:
        pass
    return users_by_id

@router.get("/{gallery_id}/comments", response_model=CommentsPaginatedResponse)
async def get_gallery_comments(
    gallery_id: int,
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    db: AsyncSession = Depends(get_db)
):
    """Получение комментариев к галерее с пагинацией"""
    
    # Проверяем существование галереи
    gallery_query = select(Gallery).where(
        Gallery.id == gallery_id,
        Gallery.is_deleted == False
    )
    gallery = await db.scalar(gallery_query)
    
    if not gallery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Галерея не найдена"
        )
    
    # Общее количество комментариев
    count_query = select(func.count(GalleryComment.id)).where(
        GalleryComment.gallery_id == gallery_id,
        GalleryComment.is_deleted == False
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Получаем комментарии с пагинацией
    offset = (page - 1) * page_size
    comments_query = select(GalleryComment).where(
        GalleryComment.gallery_id == gallery_id,
        GalleryComment.is_deleted == False
    ).order_by(GalleryComment.created_at).offset(offset).limit(page_size)
    
    result = await db.execute(comments_query)
    comments = result.scalars().all()
    
    # Получаем информацию об авторах комментариев
    author_ids = [comment.author_id for comment in comments]
    users_by_id = await get_users_batch(author_ids)
    
    # Формируем ответ
    comments_response = []
    for comment in comments:
        comment_data = CommentResponse(
            id=comment.id,
            gallery_id=comment.gallery_id,
            author_id=comment.author_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            is_edited=comment.is_edited,
            author=users_by_id.get(comment.author_id)
        )
        comments_response.append(comment_data)
    
    pages = math.ceil(total / page_size)
    
    return CommentsPaginatedResponse(
        items=comments_response,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )

@router.post("/{gallery_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    gallery_id: int,
    comment_data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создание нового комментария к галерее"""
    
    # Проверяем существование галереи
    gallery_query = select(Gallery).where(
        Gallery.id == gallery_id,
        Gallery.is_deleted == False
    )
    gallery = await db.scalar(gallery_query)
    
    if not gallery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Галерея не найдена"
        )
    
    # Создаем комментарий
    new_comment = GalleryComment(
        gallery_id=gallery_id,
        author_id=current_user.id,
        content=comment_data.content,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(new_comment)
    
    # Увеличиваем счетчик комментариев в галерее
    await db.execute(
        update(Gallery)
        .where(Gallery.id == gallery_id)
        .values(comments_count=Gallery.comments_count + 1)
    )
    
    await db.commit()
    await db.refresh(new_comment)
    
    # Получаем информацию об авторе
    author_info = await get_user_info(current_user.id)
    
    return CommentResponse(
        id=new_comment.id,
        gallery_id=new_comment.gallery_id,
        author_id=new_comment.author_id,
        content=new_comment.content,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at,
        is_edited=new_comment.is_edited,
        author=author_info
    )

@router.put("/{gallery_id}/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    gallery_id: int,
    comment_id: int,
    comment_data: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновление комментария (только автором)"""
    
    # Получаем комментарий
    comment_query = select(GalleryComment).where(
        GalleryComment.id == comment_id,
        GalleryComment.gallery_id == gallery_id,
        GalleryComment.is_deleted == False
    )
    comment = await db.scalar(comment_query)
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Комментарий не найден"
        )
    
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для редактирования комментария"
        )
    
    # Обновляем комментарий
    comment.content = comment_data.content
    comment.is_edited = True
    comment.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(comment)
    
    # Получаем информацию об авторе
    author_info = await get_user_info(current_user.id)
    
    return CommentResponse(
        id=comment.id,
        gallery_id=comment.gallery_id,
        author_id=comment.author_id,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_edited=comment.is_edited,
        author=author_info
    )

@router.delete("/{gallery_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    gallery_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Удаление комментария (только автором)"""
    
    # Получаем комментарий
    comment_query = select(GalleryComment).where(
        GalleryComment.id == comment_id,
        GalleryComment.gallery_id == gallery_id,
        GalleryComment.is_deleted == False
    )
    comment = await db.scalar(comment_query)
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Комментарий не найден"
        )
    
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для удаления комментария"
        )
    
    # Логическое удаление комментария
    comment.is_deleted = True
    
    # Уменьшаем счетчик комментариев в галерее
    await db.execute(
        update(Gallery)
        .where(Gallery.id == gallery_id)
        .values(comments_count=func.greatest(0, Gallery.comments_count - 1))
    )
    
    await db.commit()
    
    return None 