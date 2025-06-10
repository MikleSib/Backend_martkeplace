import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

# Настройка bearer токена
security = HTTPBearer()

# URL сервисов
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user_service:8002")

class User:
    """Класс для хранения данных пользователя"""
    def __init__(self, id: int, username: str, email: str, role: str):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
        
    @property
    def is_moderator(self) -> bool:
        return self.role == "moderator" or self.role == "admin"

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Получение текущего пользователя из ID
    В микросервисной архитектуре проверка токена происходит в API Gateway,
    а в gallery_service передается только ID пользователя
    """
    try:
        # ID пользователя передается в заголовке Authorization как Bearer token
        # Если формат "Bearer 123", извлекаем числовую часть
        token = credentials.credentials
        
        # Проверяем формат
        if token.isdigit():
            # Если передан просто числовой ID
            user_id = int(token)
        else:
            # Если передана строка Bearer token, проверяем наличие префикса Bearer
            if token.startswith("Bearer "):
                # Удаляем префикс и пробел
                token = token[7:]
            
            try:
                # Пытаемся извлечь ID из токена
                user_id = int(token)
            except ValueError:
                raise ValueError("Token is not a valid user ID")
        
        # Для получения дополнительных данных пользователя делаем запрос к user_service
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
                
                if response.status_code == 200:
                    user_data = response.json()
                    return User(
                        id=user_id,
                        username=user_data.get("username", "Неизвестный"),
                        email=user_data.get("email", ""),
                        role=user_data.get("role", "user")
                    )
            except httpx.RequestError:
                # Если сервис пользователей недоступен, создаем объект с минимальными данными
                pass
        
        # Если не удалось получить данные из user_service, возвращаем объект только с ID
        return User(
            id=user_id,
            username="Пользователь",
            email="",
            role="user"
        )
            
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user ID: {str(e)}"
        )

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Получение текущего пользователя (опционально)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None 