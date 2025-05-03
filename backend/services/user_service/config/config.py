from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum
import os

# Конфигурация базы данных
DB_USER = os.getenv("DB_USER_USER", "postgres")
DB_PASSWORD = os.getenv("DB_USER_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_USER_HOST", "db_user")
DB_PORT = os.getenv("DB_USER_PORT", "5432")
DB_NAME = os.getenv("DB_USER_NAME", "db_user")

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

class UserRole(str, Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class ProfileCreate(BaseModel):
    user_id: int
    username: str
    full_name: str
    about_me: Optional[str] = None
    avatar: Optional[str] = None
    signature: Optional[str] = None
    posts_count: int = 0
    role: UserRole = UserRole.USER

class ProfileResponse(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str
    about_me: Optional[str] = None
    avatar: Optional[str] = None
    signature: Optional[str] = None
    registration_date: Optional[datetime] = None
    posts_count: int = 0
    role: str = "user"
    
    class Config:
        from_attributes = True
