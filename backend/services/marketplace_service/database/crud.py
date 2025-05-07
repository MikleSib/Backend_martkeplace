from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc, or_, func
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
        base_query = select(Product).where(Product.status != "out-of-stock")
        
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
        query = select(Product).options(selectinload(Product.company)).where(Product.status != "out-of-stock")
        
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
    
    async def hide_product(self, product_id: int) -> Optional[Product]:
        """
        Скрывает товар, устанавливая статус 'out-of-stock'
        
        Args:
            product_id (int): ID товара для скрытия
            
        Returns:
            Optional[Product]: Обновленный товар или None, если товар не найден
        """
        product = await self.get_product(product_id)
        if not product:
            return None
        
        product.status = "out-of-stock"
        await self.db.commit()
        
        # Загружаем обновленный продукт со связанной компанией
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.company))
            .where(Product.id == product_id)
        )
        return result.scalars().first()
    
    async def delete_product(self, product_id: int) -> bool:
        """
        Полностью удаляет товар из базы данных
        
        Args:
            product_id (int): ID товара для удаления
            
        Returns:
            bool: True если товар был удален, False если товар не найден
        """
        product = await self.get_product(product_id)
        if not product:
            return False
        
        await self.db.delete(product)
        await self.db.commit()
        return True

    async def get_filters(self) -> Dict[str, Any]:
        """
        Получает актуальные фильтры для фронтенда
        
        Returns:
            Dict[str, Any]: Словарь с фильтрами:
                - categories: List[str] - список уникальных категорий
                - stores: List[str] - список уникальных магазинов
                - marketplaces: List[str] - список уникальных маркетплейсов
                - price_range: Dict[str, float] - минимальная и максимальная цена
        """
        # Получаем уникальные категории
        categories_query = select(Product.category).distinct().where(Product.status != "out-of-stock")
        categories_result = await self.db.execute(categories_query)
        categories = [row[0] for row in categories_result.all() if row[0]]

        # Получаем уникальные магазины
        stores_query = select(Product.store).distinct().where(Product.status != "out-of-stock")
        stores_result = await self.db.execute(stores_query)
        stores = [row[0] for row in stores_result.all() if row[0]]

        # Получаем уникальные маркетплейсы
        marketplaces_query = select(Product.marketplace).distinct().where(Product.status != "out-of-stock")
        marketplaces_result = await self.db.execute(marketplaces_query)
        marketplaces = [row[0] for row in marketplaces_result.all() if row[0]]

        # Получаем минимальную и максимальную цены
        price_query = select(
            func.min(Product.price).label('min_price'),
            func.max(Product.price).label('max_price')
        ).where(Product.status != "out-of-stock")
        price_result = await self.db.execute(price_query)
        price_row = price_result.first()
        
        price_range = {
            "min": float(price_row.min_price) if price_row.min_price else 0.0,
            "max": float(price_row.max_price) if price_row.max_price else 0.0
        }

        return {
            "categories": categories,
            "stores": stores,
            "marketplaces": marketplaces,
            "price_range": price_range
        } 