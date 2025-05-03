from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

class ImageCreate(BaseModel):
    """Схема для добавления изображения к сообщению"""
    image_url: str
    thumbnail_url: Optional[str] = None
    dimensions: Optional[str] = None  # например "1920x1080"
    size: Optional[int] = None  # в байтах

class PostBase(BaseModel):
    """Базовая схема для сообщений форума"""
    content: str = Field(..., min_length=1)
    quoted_post_id: Optional[int] = None

class PostCreate(PostBase):
    """Схема для создания сообщения"""
    topic_id: int
    images: Optional[List[ImageCreate]] = None

class PostUpdate(BaseModel):
    """Схема для обновления сообщения"""
    content: Optional[str] = Field(None, min_length=1)

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

class ImageResponse(BaseModel):
    """Схема для ответа с данными изображения"""
    id: int
    image_url: str
    thumbnail_url: Optional[str] = None
    dimensions: Optional[str] = None
    
    class Config:
        from_attributes = True

class PostResponse(PostBase):
    """Схема для ответа с данными сообщения"""
    id: int
    topic_id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    is_topic_starter: bool
    is_edited: bool
    likes_count: int
    dislikes_count: int
    user: Optional[UserInfo] = None
    images: List[ImageResponse] = []
    
    class Config:
        from_attributes = True

class PostDetailResponse(PostResponse):
    """Расширенная схема сообщения с информацией об авторе и изображениях"""
    author_username: str
    author_avatar: Optional[str] = None
    author_signature: Optional[str] = None
    author_post_count: int
    user: Optional[UserInfo] = None
    quoted_content: Optional[str] = None
    quoted_author: Optional[str] = None
    quoted_post_user: Optional[UserInfo] = None
    
    class Config:
        from_attributes = True 