from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from .models import Product, Company

class MarketplaceCRUD:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_product(self, **kwargs) -> Product:
        try:
            # Извлекаем данные компании из kwargs
            company_data = kwargs.pop('company', None)
            
            # Создаем продукт
            product = Product(**kwargs)
            self.db.add(product)
            await self.db.commit()
            await self.db.refresh(product)
            
            # Если есть данные компании, создаем запись компании
            if company_data:
                company = Company(product_id=product.id, **company_data)
                self.db.add(company)
                await self.db.commit()
            
            # Загружаем продукт со связанной компанией
            result = await self.db.execute(
                select(Product)
                .options(selectinload(Product.company))
                .where(Product.id == product.id)
            )
            return result.scalars().first()
        except Exception as e:
            await self.db.rollback()
            raise e
    
    async def get_product(self, product_id: int) -> Optional[Product]:
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.company))
            .where(Product.id == product_id)
        )
        return result.scalars().first()
    
    async def get_products(
        self, 
        skip: int = 0, 
        limit: int = 30,
        search: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        store: Optional[str] = None,
        sort: Optional[str] = None
    ) -> Dict[str, Any]:
        # Базовый запрос для фильтрации
        base_query = select(Product)
        
        # Применяем фильтры
        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Product.title.ilike(search_term),
                    Product.brand.ilike(search_term),
                    Product.category.ilike(search_term)
                )
            )
        
        if category:
            base_query = base_query.where(Product.category == category)
            
        if brand:
            base_query = base_query.where(Product.brand == brand)
            
        if store:
            base_query = base_query.where(Product.store == store)
        
        # Получаем общее количество записей для пагинации
        count_query = select(Product.id).select_from(base_query.subquery())
        result = await self.db.execute(count_query)
        total = len(result.scalars().all())
        
        # Создаем запрос для получения продуктов со связанными данными
        query = select(Product).options(selectinload(Product.company))
        
        # Применяем те же фильтры
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Product.title.ilike(search_term),
                    Product.brand.ilike(search_term),
                    Product.category.ilike(search_term)
                )
            )
        
        if category:
            query = query.where(Product.category == category)
            
        if brand:
            query = query.where(Product.brand == brand)
            
        if store:
            query = query.where(Product.store == store)
        
        # Применяем сортировку
        if sort:
            if sort == "price-asc":
                query = query.order_by(asc(Product.price))
            elif sort == "price-desc":
                query = query.order_by(desc(Product.price))
            elif sort == "rating":
                query = query.order_by(desc(Product.rating))
            elif sort == "discount":
                query = query.order_by(desc(Product.discount))
        
        # Применяем пагинацию
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        return {
            "total": total,
            "page": skip // limit + 1,
            "limit": limit,
            "products": products
        }
    
    async def update_product(self, product_id: int, **kwargs) -> Optional[Product]:
        company_data = kwargs.pop('company', None)
        
        product = await self.get_product(product_id)
        if not product:
            return None
        
        # Обновляем основные поля продукта
        for key, value in kwargs.items():
            setattr(product, key, value)
        
        # Обновляем информацию о компании, если предоставлена
        if company_data and product.company:
            for key, value in company_data.items():
                setattr(product.company, key, value)
        elif company_data and not product.company:
            company = Company(product_id=product.id, **company_data)
            self.db.add(company)
        
        await self.db.commit()
        
        # Загружаем обновленный продукт со связанной компанией
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.company))
            .where(Product.id == product_id)
        )
        return result.scalars().first()
    
    async def delete_product(self, product_id: int) -> bool:
        product = await self.get_product(product_id)
        if not product:
            return False
        
        await self.db.delete(product)
        await self.db.commit()
        return True 