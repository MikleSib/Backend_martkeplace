from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Параметры пагинации"""
    page: int = Field(1, ge=1, description="Номер страницы")
    page_size: int = Field(20, ge=1, le=100, description="Размер страницы")
    
class PaginatedResponse(BaseModel, Generic[T]):
    """Обобщенный ответ с пагинацией"""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int
    
class HealthResponse(BaseModel):
    """Ответ для проверки работоспособности сервиса"""
    status: str = "ok"
    version: str

class MessageResponse(BaseModel):
    """Ответ с простым сообщением"""
    message: str
    
class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    detail: str 