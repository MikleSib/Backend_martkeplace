import os
from typing import Optional

class Settings:
    """Настройки для сервиса форума"""
    
    # Сервис
    SERVICE_NAME: str = "forum_service"
    VERSION: str = "0.1.0"
    
    # База данных
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # Подключения к другим сервисам
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8001")
    USER_SERVICE_URL: str = os.getenv("USER_SERVICE_URL", "http://user_service:8000/api/v1")
    REDIS_SERVICE_URL: str = os.getenv("REDIS_SERVICE_URL", "http://redis_service:8003")
    FILE_SERVICE_URL: str = os.getenv("FILE_SERVICE_URL", "http://file_service:8000/api/v1")
    FORUM_URL: str = os.getenv("FORUM_URL", "http://localhost:8000/forum")
    
    # Настройки API
    API_PREFIX: str = "/api/v1"
    
    # Redis для WebSocket
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    
    # Настройки загрузки изображений
    MAX_IMAGE_SIZE: int = 8 * 1024 * 1024  # 8 МБ
    MAX_IMAGES_PER_POST: int = 5
    ALLOWED_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "gif"]
    UPLOAD_FOLDER: str = "/app/uploads/forum"
    
    # Лимиты и пагинация
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

settings = Settings() 