from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from database.models import NotificationType, ReferenceType

class NotificationResponse(BaseModel):
    """Схема для ответа с данными уведомления"""
    id: int
    user_id: int
    sender_id: int
    sender_username: str
    sender_avatar: Optional[str] = None
    type: NotificationType
    content: Optional[str] = None
    reference_id: int
    reference_type: ReferenceType
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationCreate(BaseModel):
    """Схема для создания уведомления"""
    user_id: int
    sender_id: int
    type: NotificationType
    content: Optional[str] = None
    reference_id: int
    reference_type: ReferenceType

class NotificationUpdate(BaseModel):
    """Схема для обновления уведомления"""
    is_read: bool = True

class NotificationCountResponse(BaseModel):
    """Схема для ответа с количеством непрочитанных уведомлений"""
    unread_count: int 