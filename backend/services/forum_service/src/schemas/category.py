from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

class CategoryBase(BaseModel):
    """Базовая схема для категорий форума"""
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    order: int = 0
    parent_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    """Схема для создания категории"""
    pass

class CategoryUpdate(BaseModel):
    """Схема для обновления категории"""
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    order: Optional[int] = None
    parent_id: Optional[int] = None

class CategoryResponse(CategoryBase):
    """Схема для ответа с данными категории"""
    id: int
    topics_count: int = 0
    messages_count: int = 0
    
    class Config:
        from_attributes = True

class CategoryDetailResponse(CategoryResponse):
    """Расширенная схема категории с подкатегориями"""
    subcategories: List['CategoryResponse'] = []
    
    class Config:
        from_attributes = True 