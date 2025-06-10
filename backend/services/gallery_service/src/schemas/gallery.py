from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class ImageCreate(BaseModel):
    """Схема для добавления изображения к галерее"""
    image_url: str
    thumbnail_url: Optional[str] = None
    dimensions: Optional[str] = None
    size: Optional[int] = None
    order_index: int = 0

class ImageResponse(BaseModel):
    """Схема для ответа с данными изображения"""
    id: int
    image_url: str
    thumbnail_url: Optional[str] = None
    dimensions: Optional[str] = None
    size: int
    order_index: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserInfo(BaseModel):
    """Информация о пользователе"""
    id: int
    username: str
    fullname: Optional[str] = None
    avatar: Optional[str] = None
    registration_date: Optional[datetime] = None
    posts_count: int = 0
    role: str = "user"
    
    class Config:
        from_attributes = True

class GalleryCreate(BaseModel):
    """Схема для создания галереи"""
    title: str = Field(..., min_length=1, max_length=255)
    images: List[ImageCreate] = Field(..., min_items=1, max_items=5)

class GalleryUpdate(BaseModel):
    """Схема для обновления галереи"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)

class GalleryPreview(BaseModel):
    """Схема для списка галерей (с одной превью картинкой)"""
    id: int
    title: str
    author_id: int
    created_at: datetime
    views_count: int
    likes_count: int
    dislikes_count: int
    comments_count: int
    preview_image: Optional[ImageResponse] = None
    author: Optional[UserInfo] = None
    
    class Config:
        from_attributes = True

class GalleryDetail(BaseModel):
    """Схема для детального просмотра галереи (со всеми картинками)"""
    id: int
    title: str
    author_id: int
    created_at: datetime
    updated_at: datetime
    views_count: int
    likes_count: int
    dislikes_count: int
    comments_count: int
    images: List[ImageResponse] = []
    author: Optional[UserInfo] = None
    
    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    """Схема для пагинированного ответа"""
    items: List[GalleryPreview]
    total: int
    page: int
    page_size: int
    pages: int 