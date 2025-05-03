import math
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from src.schemas.common import PaginatedResponse

T = TypeVar("T")

async def paginate(
    db: AsyncSession,
    query: Select,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    response_model: Optional[Type[BaseModel]] = None
) -> Dict[str, Any]:
    """
    Пагинация результатов для запроса в базу данных
    
    Args:
        db: Сессия базы данных
        query: SQLAlchemy запрос
        page: Номер страницы (начиная с 1)
        page_size: Размер страницы
        response_model: Тип модели ответа (для преобразования результатов)
    
    Returns:
        Dict с параметрами для создания PaginatedResponse
    """
    # Получаем общее количество записей для пагинации
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Добавляем лимит и смещение для пагинации
    query = query.limit(page_size).offset((page - 1) * page_size)
    
    # Выполняем запрос с пагинацией
    result = await db.execute(query)
    items = result.scalars().all()
    
    # Рассчитываем общее количество страниц
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages
    } 