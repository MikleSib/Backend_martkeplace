from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from .gallery import UserInfo

class CommentCreate(BaseModel):
    """Схема для создания комментария"""
    content: str = Field(..., min_length=1, max_length=1000)

class CommentUpdate(BaseModel):
    """Схема для обновления комментария"""
    content: str = Field(..., min_length=1, max_length=1000)

class CommentResponse(BaseModel):
    """Схема для ответа с данными комментария"""
    id: int
    gallery_id: int
    author_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    author: Optional[UserInfo] = None
    
    class Config:
        from_attributes = True

class CommentsPaginatedResponse(BaseModel):
    """Схема для пагинированного ответа с комментариями"""
    items: List[CommentResponse]
    total: int
    page: int
    page_size: int
    pages: int

class MessageResponse(BaseModel):
    """Схема для простого ответа с сообщением"""
    message: str 