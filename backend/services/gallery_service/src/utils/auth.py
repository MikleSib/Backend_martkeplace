import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

# Схема для пользователя
class User(BaseModel):
    id: int
    username: str
    email: str
    role: str = "user"

# Настройка bearer токена
security = HTTPBearer()

# URL сервиса аутентификации
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8001")

async def verify_token(token: str) -> Optional[User]:
    """Проверка JWT токена через auth_service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/auth/check_token",
                params={"token": token}
            )
            
            if response.status_code == 200:
                user_data = response.json()
                if user_data.get("valid", False):
                    return User(
                        id=user_data["user_id"],
                        username=user_data["username"],
                        email=user_data["email"],
                        role="admin" if user_data.get("is_admin", False) else "user"
                    )
    except httpx.RequestError:
        pass
    
    return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Получение текущего пользователя из JWT токена"""
    token = credentials.credentials
    user = await verify_token(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """Получение текущего пользователя (опционально)"""
    if not credentials:
        return None
    
    token = credentials.credentials
    return await verify_token(token) 