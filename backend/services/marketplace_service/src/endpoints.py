from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from database import get_db, MarketplaceCRUD
from config import (
    ProductCreate, ProductUpdate, ProductResponse, ProductsListResponse
)
import os

router = APIRouter(prefix="/marketplace")

@router.get("/products", response_model=ProductsListResponse)
async def get_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    store: Optional[str] = Query(None, pattern="^(ozon|wildberries|aliexpress|other)$"),
    sort: Optional[str] = Query(None, pattern="^(price-asc|price-desc|rating|discount)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список продуктов с применением фильтров, сортировки и пагинации
    
    - **search**: Поиск по названию, бренду, категории
    - **category**: Фильтрация по категории товара
    - **brand**: Фильтрация по бренду товара
    - **store**: Фильтрация по маркетплейсу (ozon, wildberries, aliexpress, other)
    - **sort**: Сортировка (price-asc, price-desc, rating, discount)
    - **page**: Номер страницы (начинается с 1)
    - **limit**: Количество товаров на странице (от 1 до 100)
    """
    
    crud = MarketplaceCRUD(db)
    
    # Вычисляем смещение для пагинации
    skip = (page - 1) * limit
    
    return await crud.get_products(
        skip=skip,
        limit=limit,
        search=search,
        category=category,
        brand=brand,
        store=store,
        sort=sort
    )

@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить детальную информацию о товаре по ID
    """
    crud = MarketplaceCRUD(db)
    product = await crud.get_product(product_id)
    
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    return product

@router.post("/products", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Создать новый товар
    """
    crud = MarketplaceCRUD(db)
    
    try:
        # Преобразуем Pydantic модель в словарь
        product_data = product.model_dump()
        
        # Создаем товар
        created_product = await crud.create_product(**product_data)
        return created_product
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating marketplace product: {str(e)}"
        )

@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product: ProductUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить существующий товар по ID
    """
    crud = MarketplaceCRUD(db)
    
    # Проверяем, существует ли товар
    existing_product = await crud.get_product(product_id)
    if not existing_product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    # Преобразуем Pydantic модель в словарь, исключая None значения
    update_data = {k: v for k, v in product.model_dump().items() if v is not None}
    
    updated_product = await crud.update_product(product_id, **update_data)
    return updated_product

@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить товар по ID
    """
    crud = MarketplaceCRUD(db)
    
    # Проверяем, существует ли товар
    existing_product = await crud.get_product(product_id)
    if not existing_product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    success = await crud.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось удалить товар")
    
    return {"message": "Товар успешно удален"}

@router.post("/admin/products/{product_id}/hide", response_model=ProductResponse)
async def hide_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Скрыть товар (только для администраторов)
    
    - **product_id**: ID товара для скрытия
    
    Returns:
        ProductResponse: Обновленный товар со статусом 'hidden'
        
    Raises:
        HTTPException: Если товар не найден
    """
    crud = MarketplaceCRUD(db)
    product = await crud.hide_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.delete("/admin/products/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить товар (только для администраторов)
    
    - **product_id**: ID товара для удаления
    
    Returns:
        None: Товар успешно удален
        
    Raises:
        HTTPException: Если товар не найден
    """
    crud = MarketplaceCRUD(db)
    if not await crud.delete_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found") 