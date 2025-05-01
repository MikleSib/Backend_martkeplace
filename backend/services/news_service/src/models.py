from enum import Enum
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class NewsCategory(str, Enum):
    MAIN = "news"  # Основные новости
    GUIDES = "guides"  # Гайды
    EVENTS = "events"  # События
    FISH_SPECIES = "fish_species"  # Виды рыб
    # В будущем можно добавить другие категории

class NewsContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"

class NewsContent(BaseModel):
    type: NewsContentType
    content: str  # Текст или URL для медиа
    order: int  # Порядок отображения

class NewsBase(BaseModel):
    title: str
    category: NewsCategory
    contents: List[NewsContent]

class NewsCreate(NewsBase):
    pass

class NewsUpdate(NewsBase):
    pass

class News(NewsBase):
    id: int
    created_at: datetime
    updated_at: datetime
    author_id: int  # ID администратора

    class Config:
        from_attributes = True 