from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

class TopicBase(BaseModel):
    """Базовая модель для темы форума"""
    title: str = Field(..., min_length=5, max_length=255)
    category_id: int
    tags: Optional[List[str]] = Field(None, max_items=5)
    
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 5:
            raise ValueError('Максимальное количество тегов - 5')
        return v

class TopicCreate(TopicBase):
    """Модель для создания темы"""
    content: str = Field(..., min_length=10)
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            if len(v) > 5:
                raise ValueError('Maximum 5 tags allowed')
            for tag in v:
                if len(tag) > 20:
                    raise ValueError('Tag length cannot exceed 20 characters')
        return v

class TopicUpdate(BaseModel):
    """Модель для обновления темы"""
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    category_id: Optional[int] = None
    tags: Optional[List[str]] = Field(None, max_items=5)
    is_closed: Optional[bool] = None
    is_pinned: Optional[bool] = None
    
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 5:
            raise ValueError('Максимальное количество тегов - 5')
        return v

class TopicResponse(BaseModel):
    """Модель ответа с темой форума"""
    id: int
    title: str
    category_id: int
    author_id: int
    created_at: datetime
    is_closed: bool
    is_pinned: bool
    views_count: int
    posts_count: int
    tags: Optional[List[str]] = None
    last_post_id: Optional[int] = None
    last_post_author_id: Optional[int] = None
    last_post_date: Optional[datetime] = None
    # Информация о пользователе
    author_username: Optional[str] = None
    author_fullname: Optional[str] = None
    author_avatar: Optional[str] = None
    # Информация об авторе последнего сообщения
    last_post_author_username: Optional[str] = None
    last_post_author_avatar: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TopicDetailResponse(TopicResponse):
    """Модель ответа с детальной информацией о теме"""
    category_title: str 