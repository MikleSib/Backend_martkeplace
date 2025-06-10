from datetime import datetime
from typing import List, Optional
import math
import httpx
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.database import get_db
from database.models import Gallery, GalleryImage
from src.schemas.gallery import (
    GalleryCreate, GalleryUpdate, GalleryDetail, GalleryPreview, 
    PaginatedResponse, UserInfo, ImageCreate, ImageResponse
)
from src.schemas.comment import MessageResponse
from src.utils.auth import User, get_current_user

router = APIRouter(prefix="/galleries", tags=["galleries"])

# URL сервисов
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user_service:8002")
FILE_SERVICE_URL = os.getenv("FILE_SERVICE_URL", "http://file_service:8005")

async def get_user_info(user_id: int) -> Optional[UserInfo]:
    """Получение информации о пользователе из user_service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
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
            # Как в forum_service - получаем пользователей по одному
            for user_id in user_ids:
                try:
                    response = await client.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
                    if response.status_code == 200:
                        user_data = response.json()
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
    except Exception:
        pass
    return users_by_id

@router.post("/upload_image", status_code=status.HTTP_201_CREATED)
async def upload_gallery_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Загрузка изображения для галереи"""
    try:
        # Проверяем MIME тип файла
        content_type = file.content_type.lower()
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Загружаемый файл должен быть изображением"
            )
            
        # Ограничение размера файла (8MB)
        MAX_FILE_SIZE = 8 * 1024 * 1024
        
        async with httpx.AsyncClient() as client:
            file_content = await file.read()
            
            if len(file_content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Размер файла превышает максимально допустимый (8MB)"
                )
                
            await file.seek(0)
            
            files = {"file": (file.filename, file.file, file.content_type)}
            response = await client.post(f"{FILE_SERVICE_URL}/upload", files=files)
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Ошибка при загрузке файла: {response.text}"
                )
                
            file_data = response.json()
            
            # Получаем размеры изображения
            dimensions = None
            try:
                from PIL import Image as PILImage
                from io import BytesIO
                
                img = PILImage.open(BytesIO(file_content))
                dimensions = f"{img.width}x{img.height}"
            except Exception:
                pass
                
            return {
                "image_url": file_data["url"],
                "thumbnail_url": file_data.get("thumbnail_url", file_data["url"]),
                "size": file_data["size"],
                "dimensions": dimensions,
                "filename": file_data["filename"],
                "content_type": file.content_type
            }
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при взаимодействии с файловым сервисом: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Произошла ошибка при загрузке изображения: {str(e)}"
        )

@router.post("", response_model=GalleryDetail, status_code=status.HTTP_201_CREATED)
async def create_gallery(
    gallery_data: GalleryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создание новой фотогалереи"""
    # Создаем галерею
    new_gallery = Gallery(
        title=gallery_data.title,
        author_id=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(new_gallery)
    await db.flush()
    
    # Добавляем изображения
    gallery_images = []
    for i, img_data in enumerate(gallery_data.images):
        image = GalleryImage(
            gallery_id=new_gallery.id,
            image_url=img_data.image_url,
            thumbnail_url=img_data.thumbnail_url,
            dimensions=img_data.dimensions,
            size=img_data.size or 0,
            order_index=i,
            created_at=datetime.utcnow()
        )
        db.add(image)
        gallery_images.append(image)
    
    await db.commit()
    await db.refresh(new_gallery)
    
    # Получаем информацию об авторе
    author_info = await get_user_info(current_user.id)
    
    # Формируем ответ
    images_response = [
        ImageResponse(
            id=img.id,
            image_url=img.image_url,
            thumbnail_url=img.thumbnail_url,
            dimensions=img.dimensions,
            size=img.size,
            order_index=img.order_index,
            created_at=img.created_at
        )
        for img in gallery_images
    ]
    
    return GalleryDetail(
        id=new_gallery.id,
        title=new_gallery.title,
        author_id=new_gallery.author_id,
        created_at=new_gallery.created_at,
        updated_at=new_gallery.updated_at,
        views_count=new_gallery.views_count,
        likes_count=new_gallery.likes_count,
        dislikes_count=new_gallery.dislikes_count,
        comments_count=new_gallery.comments_count,
        images=images_response,
        author=author_info
    )

@router.get("", response_model=PaginatedResponse)
async def get_galleries(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(12, ge=1, le=50, description="Размер страницы"),
    author_id: Optional[int] = Query(None, description="ID автора для фильтрации"),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка галерей с пагинацией (только превью)"""
    
    # Базовый запрос
    query = select(Gallery).where(Gallery.is_deleted == False)
    
    # Фильтрация по автору
    if author_id:
        query = query.where(Gallery.author_id == author_id)
    
    # Общее количество
    count_query = select(func.count(Gallery.id)).where(Gallery.is_deleted == False)
    if author_id:
        count_query = count_query.where(Gallery.author_id == author_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Пагинация
    offset = (page - 1) * page_size
    query = query.order_by(desc(Gallery.created_at)).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    galleries = result.scalars().all()
    
    # Получаем первые изображения для каждой галереи
    gallery_ids = [g.id for g in galleries]
    if gallery_ids:
        # Получаем только первые изображения (с минимальным order_index)
        preview_images_query = select(GalleryImage).where(
            GalleryImage.gallery_id.in_(gallery_ids),
            GalleryImage.order_index == 0
        )
        preview_images_result = await db.execute(preview_images_query)
        preview_images = preview_images_result.scalars().all()
        
        # Создаем словарь галерея_id -> превью_изображение
        preview_images_dict = {img.gallery_id: img for img in preview_images}
    else:
        preview_images_dict = {}
    
    # Получаем информацию об авторах
    author_ids = [g.author_id for g in galleries]
    users_by_id = await get_users_batch(author_ids)
    
    # Формируем ответ
    gallery_previews = []
    for gallery in galleries:
        preview_image = preview_images_dict.get(gallery.id)
        preview_image_response = None
        
        if preview_image:
            preview_image_response = ImageResponse(
                id=preview_image.id,
                image_url=preview_image.image_url,
                thumbnail_url=preview_image.thumbnail_url,
                dimensions=preview_image.dimensions,
                size=preview_image.size,
                order_index=preview_image.order_index,
                created_at=preview_image.created_at
            )
        
        gallery_preview = GalleryPreview(
            id=gallery.id,
            title=gallery.title,
            author_id=gallery.author_id,
            created_at=gallery.created_at,
            views_count=gallery.views_count,
            likes_count=gallery.likes_count,
            dislikes_count=gallery.dislikes_count,
            comments_count=gallery.comments_count,
            preview_image=preview_image_response,
            author=users_by_id.get(gallery.author_id)
        )
        gallery_previews.append(gallery_preview)
    
    pages = math.ceil(total / page_size)
    
    return PaginatedResponse(
        items=gallery_previews,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )

@router.get("/{gallery_id}", response_model=GalleryDetail)
async def get_gallery_detail(
    gallery_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение детальной информации о галерее (со всеми изображениями)"""
    
    # Получаем галерею с изображениями
    query = select(Gallery).options(
        selectinload(Gallery.images)
    ).where(
        Gallery.id == gallery_id,
        Gallery.is_deleted == False
    )
    
    result = await db.execute(query)
    gallery = result.scalar_one_or_none()
    
    if not gallery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Галерея не найдена"
        )
    
    # Увеличиваем счетчик просмотров
    await db.execute(
        update(Gallery)
        .where(Gallery.id == gallery_id)
        .values(views_count=Gallery.views_count + 1)
    )
    await db.commit()
    
    # Получаем информацию об авторе
    author_info = await get_user_info(gallery.author_id)
    
    # Сортируем изображения по order_index
    sorted_images = sorted(gallery.images, key=lambda x: x.order_index)
    
    # Формируем ответ
    images_response = [
        ImageResponse(
            id=img.id,
            image_url=img.image_url,
            thumbnail_url=img.thumbnail_url,
            dimensions=img.dimensions,
            size=img.size,
            order_index=img.order_index,
            created_at=img.created_at
        )
        for img in sorted_images
    ]
    
    return GalleryDetail(
        id=gallery.id,
        title=gallery.title,
        author_id=gallery.author_id,
        created_at=gallery.created_at,
        updated_at=gallery.updated_at,
        views_count=gallery.views_count + 1,  # Обновленное значение
        likes_count=gallery.likes_count,
        dislikes_count=gallery.dislikes_count,
        comments_count=gallery.comments_count,
        images=images_response,
        author=author_info
    )

@router.put("/{gallery_id}", response_model=GalleryDetail)
async def update_gallery(
    gallery_id: int,
    gallery_data: GalleryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновление галереи (только владельцем)"""
    
    query = select(Gallery).where(
        Gallery.id == gallery_id,
        Gallery.is_deleted == False
    )
    result = await db.execute(query)
    gallery = result.scalar_one_or_none()
    
    if not gallery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Галерея не найдена"
        )
    
    if gallery.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для редактирования галереи"
        )
    
    # Обновляем данные
    if gallery_data.title is not None:
        gallery.title = gallery_data.title
        gallery.updated_at = datetime.utcnow()
    
    await db.commit()
    
    # Возвращаем обновленную галерею
    return await get_gallery_detail(gallery_id, db)

@router.delete("/{gallery_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gallery(
    gallery_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Удаление галереи (только владельцем)"""
    
    query = select(Gallery).where(
        Gallery.id == gallery_id,
        Gallery.is_deleted == False
    )
    result = await db.execute(query)
    gallery = result.scalar_one_or_none()
    
    if not gallery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Галерея не найдена"
        )
    
    if gallery.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для удаления галереи"
        )
    
    # Логическое удаление
    gallery.is_deleted = True
    await db.commit()
    
    return None 