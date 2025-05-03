import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings

security = HTTPBearer()

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
    а в сервис форума передается только ID пользователя
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
                # Если токен не является числом, пробуем отправить его на проверку в auth_service
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.get(
                            f"{settings.AUTH_SERVICE_URL}/auth/check_token",
                            params={"token": token}
                        )
                        if response.status_code == 200:
                            user_data = response.json()
                            user_id = user_data.get("user_id")
                            if not user_id:
                                raise ValueError("User ID not found in token data")
                        else:
                            raise ValueError("Invalid token")
                    except httpx.RequestError:
                        raise ValueError("Auth service unavailable")
        
        # Для получения дополнительных данных пользователя можно сделать запрос к user_service
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{settings.USER_SERVICE_URL}/users/{user_id}"
                )
                
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