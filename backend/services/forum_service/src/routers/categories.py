from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.database import get_db
from database.models import Category, Topic
from src.schemas.category import (CategoryCreate, CategoryDetailResponse,
                                  CategoryResponse, CategoryUpdate)
from src.utils.auth import User, get_current_user
from src.utils.dependencies import check_is_admin, get_category_or_404

router = APIRouter(prefix="/categories", tags=["categories"])

async def calculate_total_counts(db: AsyncSession, categories: List[Category]) -> Dict[int, Dict[str, int]]:
    """
    Рекурсивно рассчитывает общее количество тем и сообщений для категорий, 
    включая все их подкатегории
    """
    result = {}
    
    # Получаем все подкатегории для всех категорий
    all_category_ids = [cat.id for cat in categories]
    if not all_category_ids:
        return result
        
    # Получаем все вложенные подкатегории
    all_subcategories_query = select(Category).where(Category.parent_id.in_(all_category_ids))
    all_subcategories_result = await db.execute(all_subcategories_query)
    all_subcategories = all_subcategories_result.scalars().all()
    
    # Рекурсивно вычисляем для подкатегорий
    subcategory_counts = await calculate_total_counts(db, all_subcategories)
    
    # Инициализируем счетчики для текущих категорий
    for category in categories:
        result[category.id] = {
            "topics_count": category.topics_count,
            "messages_count": category.messages_count
        }
    
    # Учитываем счетчики подкатегорий
    for subcategory in all_subcategories:
        if subcategory.parent_id in result:
            result[subcategory.parent_id]["topics_count"] += subcategory.topics_count
            result[subcategory.parent_id]["messages_count"] += subcategory.messages_count
            
            # Также добавляем сюда счетчики от вложенных подкатегорий
            if subcategory.id in subcategory_counts:
                result[subcategory.parent_id]["topics_count"] += subcategory_counts[subcategory.id]["topics_count"]
                result[subcategory.parent_id]["messages_count"] += subcategory_counts[subcategory.id]["messages_count"]
                
    return result

@router.get("", response_model=List[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db)
):
    """Получение списка всех корневых категорий"""
    query = select(Category).where(Category.parent_id.is_(None)).order_by(Category.order)
    result = await db.execute(query)
    categories = result.scalars().all()
    
    # Рассчитываем общие счетчики, включая подкатегории
    total_counts = await calculate_total_counts(db, categories)
    
    # Обновляем счетчики в ответе
    response_categories = []
    for category in categories:
        category_dict = {
            "id": category.id,
            "title": category.title,
            "description": category.description,
            "icon": category.icon,
            "order": category.order,
            "parent_id": category.parent_id,
            "topics_count": total_counts.get(category.id, {}).get("topics_count", category.topics_count),
            "messages_count": total_counts.get(category.id, {}).get("messages_count", category.messages_count)
        }
        response_categories.append(CategoryResponse.model_validate(category_dict))
    
    return response_categories

@router.get("/{category_id}", response_model=CategoryDetailResponse)
async def get_category(
    category: Category = Depends(get_category_or_404),
    db: AsyncSession = Depends(get_db)
):
    """Получение данных категории с подкатегориями"""
    # Загружаем подкатегории
    query = select(Category).where(Category.parent_id == category.id).order_by(Category.order)
    result = await db.execute(query)
    subcategories = result.scalars().all()
    
    # Рассчитываем общие счетчики для подкатегорий
    subcategory_counts = await calculate_total_counts(db, subcategories)
    
    # Подготовим улучшенные данные для подкатегорий с обновленными счетчиками
    enhanced_subcategories = []
    for subcat in subcategories:
        total_topics = subcat.topics_count
        total_messages = subcat.messages_count
        
        # Добавляем счетчики от вложенных подкатегорий
        if subcat.id in subcategory_counts:
            total_topics += subcategory_counts[subcat.id].get("topics_count", 0)
            total_messages += subcategory_counts[subcat.id].get("messages_count", 0)
            
        subcat_dict = {
            "id": subcat.id,
            "title": subcat.title,
            "description": subcat.description,
            "icon": subcat.icon,
            "order": subcat.order,
            "parent_id": subcat.parent_id,
            "topics_count": total_topics,
            "messages_count": total_messages
        }
        enhanced_subcategories.append(CategoryResponse.model_validate(subcat_dict))
    
    # Создаем ответ с подкатегориями, используя преобразование в словарь и обратно
    # Суммируем счетчики самой категории и всех подкатегорий
    total_topics = category.topics_count
    total_messages = category.messages_count
    
    for subcat in subcategories:
        if subcat.id in subcategory_counts:
            # Добавляем счетчики от всех вложенных подкатегорий
            total_topics += subcategory_counts[subcat.id].get("topics_count", 0) + subcat.topics_count
            total_messages += subcategory_counts[subcat.id].get("messages_count", 0) + subcat.messages_count
        else:
            # Только прямые счетчики подкатегории
            total_topics += subcat.topics_count
            total_messages += subcat.messages_count
    
    category_dict = {
        "id": category.id,
        "title": category.title,
        "description": category.description,
        "icon": category.icon,
        "order": category.order,
        "parent_id": category.parent_id,
        "topics_count": total_topics,
        "messages_count": total_messages,
        "subcategories": enhanced_subcategories
    }
    
    return CategoryDetailResponse.model_validate(category_dict)

@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(check_is_admin)
):
    """Создание новой категории (только для администраторов)"""
    # Проверка родительской категории, если указана
    if category_data.parent_id:
        parent_query = select(Category).where(Category.id == category_data.parent_id)
        parent = await db.scalar(parent_query)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Родительская категория с ID {category_data.parent_id} не найдена"
            )
    
    # Создаем новую категорию
    new_category = Category(**category_data.model_dump())
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)
    
    return new_category

@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_data: CategoryUpdate,
    category: Category = Depends(get_category_or_404),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(check_is_admin)
):
    """Обновление категории (только для администраторов)"""
    # Проверка родительской категории, если изменена
    if category_data.parent_id is not None and category_data.parent_id != category.parent_id:
        # Нельзя установить самого себя как родителя
        if category_data.parent_id == category.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Категория не может быть своим родителем"
            )
        
        # Проверка существования родительской категории
        if category_data.parent_id > 0:
            parent_query = select(Category).where(Category.id == category_data.parent_id)
            parent = await db.scalar(parent_query)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Родительская категория с ID {category_data.parent_id} не найдена"
                )
    
    # Обновляем данные категории
    for key, value in category_data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    
    await db.commit()
    await db.refresh(category)
    
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category: Category = Depends(get_category_or_404),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(check_is_admin)
):
    """Удаление категории (только для администраторов)"""
    # Проверяем наличие подкатегорий
    subcategories_query = select(Category).where(Category.parent_id == category.id)
    result = await db.execute(subcategories_query)
    subcategories = result.scalars().all()
    if subcategories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить категорию, содержащую подкатегории"
        )
    
    # Проверяем наличие тем в категории
    if category.topics_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить категорию, содержащую темы"
        )
    
    # Удаляем категорию
    await db.delete(category)
    await db.commit()
    
    return None 