from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db
from database.models import Gallery, GalleryReaction
from src.schemas.comment import MessageResponse
from src.utils.auth import User, get_current_user

router = APIRouter(prefix="/galleries", tags=["reactions"])

@router.post("/{gallery_id}/like", response_model=MessageResponse)
async def like_gallery(
    gallery_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Поставить лайк галерее"""
    
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
    
    # Проверяем существующие реакции пользователя
    reaction_query = select(GalleryReaction).where(
        GalleryReaction.gallery_id == gallery_id,
        GalleryReaction.user_id == current_user.id
    )
    existing_reaction = await db.scalar(reaction_query)
    
    if existing_reaction:
        if existing_reaction.type == "LIKE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вы уже поставили лайк этой галерее"
            )
        
        # Меняем дизлайк на лайк
        existing_reaction.type = "LIKE"
        
        # Обновляем счетчики
        await db.execute(
            update(Gallery)
            .where(Gallery.id == gallery_id)
            .values(
                likes_count=Gallery.likes_count + 1,
                dislikes_count=Gallery.dislikes_count - 1
            )
        )
    else:
        # Создаем новую реакцию
        new_reaction = GalleryReaction(
            gallery_id=gallery_id,
            user_id=current_user.id,
            type="LIKE"
        )
        db.add(new_reaction)
        
        # Увеличиваем счетчик лайков
        await db.execute(
            update(Gallery)
            .where(Gallery.id == gallery_id)
            .values(likes_count=Gallery.likes_count + 1)
        )
    
    await db.commit()
    
    return MessageResponse(message="Лайк успешно добавлен")

@router.post("/{gallery_id}/dislike", response_model=MessageResponse)
async def dislike_gallery(
    gallery_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Поставить дизлайк галерее"""
    
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
    
    # Проверяем существующие реакции пользователя
    reaction_query = select(GalleryReaction).where(
        GalleryReaction.gallery_id == gallery_id,
        GalleryReaction.user_id == current_user.id
    )
    existing_reaction = await db.scalar(reaction_query)
    
    if existing_reaction:
        if existing_reaction.type == "DISLIKE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вы уже поставили дизлайк этой галерее"
            )
        
        # Меняем лайк на дизлайк
        existing_reaction.type = "DISLIKE"
        
        # Обновляем счетчики
        await db.execute(
            update(Gallery)
            .where(Gallery.id == gallery_id)
            .values(
                dislikes_count=Gallery.dislikes_count + 1,
                likes_count=Gallery.likes_count - 1
            )
        )
    else:
        # Создаем новую реакцию
        new_reaction = GalleryReaction(
            gallery_id=gallery_id,
            user_id=current_user.id,
            type="DISLIKE"
        )
        db.add(new_reaction)
        
        # Увеличиваем счетчик дизлайков
        await db.execute(
            update(Gallery)
            .where(Gallery.id == gallery_id)
            .values(dislikes_count=Gallery.dislikes_count + 1)
        )
    
    await db.commit()
    
    return MessageResponse(message="Дизлайк успешно добавлен")

@router.delete("/{gallery_id}/reactions", response_model=MessageResponse)
async def remove_gallery_reaction(
    gallery_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Удалить реакцию пользователя на галерею"""
    
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
    
    # Ищем реакцию пользователя
    reaction_query = select(GalleryReaction).where(
        GalleryReaction.gallery_id == gallery_id,
        GalleryReaction.user_id == current_user.id
    )
    reaction = await db.scalar(reaction_query)
    
    if not reaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Реакция не найдена"
        )
    
    # Обновляем счетчики в зависимости от типа реакции
    if reaction.type == "LIKE":
        await db.execute(
            update(Gallery)
            .where(Gallery.id == gallery_id)
            .values(likes_count=Gallery.likes_count - 1)
        )
    else:
        await db.execute(
            update(Gallery)
            .where(Gallery.id == gallery_id)
            .values(dislikes_count=Gallery.dislikes_count - 1)
        )
    
    # Удаляем реакцию
    await db.delete(reaction)
    await db.commit()
    
    return MessageResponse(message="Реакция успешно удалена") 