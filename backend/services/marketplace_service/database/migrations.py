from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import Base, Product
from .db import engine
import os
import json

async def create_tables():
    """Создаем все таблицы в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_tables():
    """Удаляем все таблицы из базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def recreate_tables():
    """Пересоздаем все таблицы"""
    await drop_tables()
    await create_tables()

async def seed_sample_data(db: AsyncSession):
    """Добавляем тестовые данные"""
    # Проверяем, есть ли уже данные в таблице
    result = await db.execute(select(Product).limit(1))
    if result.scalars().first():
        return False  # Данные уже существуют
    
    # Добавляем примеры товаров
    sample_products = [
        {
            "title": "Спиннинг для рыбалки 12-в-1 спиннинг телескопический, катушка, плетенка, набор блесен, воблер, поводки",
            "price": 2499,
            "old_price": 3500,
            "discount": 28,
            "image": "https://ir-5.ozone.ru/s3/multimedia-1-y/wc1000/7429171930.jpg",
            "category": "Спиннинги",
            "brand": "Рыболов",
            "status": "in-stock",
            "rating": 4.5,
            "external_url": "https://www.ozon.ru/product/spinning-dlya-rybalki-12-v-1-spinning-teleskopicheskiy-katushka-pletenka-nabor-blesen-vobler-povodki-1234567",
            "store": "ozon",
            "description": "Комплект для рыбалки 12 в 1 включает все необходимое для успешной рыбалки: телескопическое удилище, катушку с леской, набор блесен и воблеров различных размеров, поводки и другие аксессуары.",
            "company": {
                "name": "SuperGoods",
                "rating": 4.7,
                "products_count": 128,
                "is_premium": True,
                "has_ozon_delivery": True,
                "return_period": 7
            }
        },
        {
            "title": "Катушка безынерционная рыболовная Premier Fishing Stinger 2000",
            "price": 1290,
            "old_price": 1790,
            "discount": 27,
            "image": "https://ir-6.ozone.ru/s3/multimedia-w/wc1000/6586559988.jpg",
            "category": "Катушки",
            "brand": "Premier Fishing",
            "status": "in-stock",
            "rating": 4.8,
            "external_url": "https://www.ozon.ru/product/katushka-bezinertsionnaya-rybolovnaya-premier-fishing-stinger-2000-7654321",
            "store": "ozon",
            "description": "Безынерционная катушка Stinger 2000 с передним фрикционом, 8 подшипников, передаточное число 5.2:1",
            "company": {
                "name": "Premier Fishing",
                "rating": 4.9,
                "products_count": 76,
                "is_premium": True,
                "has_ozon_delivery": True,
                "return_period": 14
            }
        },
        {
            "title": "Палатка туристическая 4-местная, водонепроницаемая, с москитной сеткой",
            "price": 4950,
            "old_price": 6500,
            "discount": 23,
            "image": "https://ir-3.ozone.ru/s3/multimedia-p/wc1000/6487607477.jpg",
            "category": "Палатки",
            "brand": "OutdoorPro",
            "status": "in-stock",
            "rating": 4.6,
            "external_url": "https://www.wildberries.ru/catalog/135790123/detail.aspx",
            "store": "wildberries",
            "description": "Туристическая палатка для 4 человек с двумя входами и тамбуром. Водонепроницаемость внешнего тента 5000 мм, дно 10000 мм.",
            "company": {
                "name": "OutdoorPro",
                "rating": 4.5,
                "products_count": 56,
                "is_premium": False,
                "has_ozon_delivery": False,
                "return_period": 30
            }
        },
        {
            "title": "Смартфон Xiaomi Redmi Note 12 Pro 8/256GB, AMOLED 120Hz, 5000mAh",
            "price": 23990,
            "old_price": 29990,
            "discount": 20,
            "image": "https://ae12.alicdn.com/kf/Sb7f64408d8324c30a95b26ae13f0b2d4p.jpg",
            "category": "Смартфоны",
            "brand": "Xiaomi",
            "status": "in-stock",
            "rating": 4.7,
            "external_url": "https://aliexpress.ru/item/1005004816282136.html",
            "store": "aliexpress",
            "description": "Смартфон Xiaomi Redmi Note 12 Pro с 8 ГБ оперативной и 256 ГБ встроенной памяти, AMOLED экраном с частотой 120 Гц и аккумулятором 5000 мАч.",
            "company": {
                "name": "Xiaomi Official Store",
                "rating": 4.9,
                "products_count": 567,
                "is_premium": True,
                "has_ozon_delivery": False,
                "return_period": 14
            }
        },
        {
            "title": "Книга 'Гарри Поттер и философский камень', иллюстрированное издание",
            "price": 1790,
            "old_price": None,
            "discount": None,
            "image": "https://ir-4.ozone.ru/s3/multimedia-k/wc1000/6497952648.jpg",
            "category": "Книги",
            "brand": None,
            "status": "out-of-stock",
            "rating": 5.0,
            "external_url": "https://www.ozon.ru/product/garri-potter-i-filosofskiy-kamen-illyustrirovannoe-izdanie-1357924",
            "store": "ozon",
            "description": "Иллюстрированное издание первой книги о приключениях Гарри Поттера с красочными иллюстрациями Джима Кея.",
            "company": {
                "name": "Издательство РОСМЭН",
                "rating": 4.8,
                "products_count": 1245,
                "is_premium": True,
                "has_ozon_delivery": True,
                "return_period": 30
            }
        }
    ]
    
    for product_data in sample_products:
        company_data = product_data.pop('company', None)
        product = Product(**product_data)
        db.add(product)
    
    await db.commit()
    
    # Добавляем связанные данные компаний
    for i, product_data in enumerate(sample_products):
        if 'company' in product_data:
            from .models import Company
            products = await db.execute(select(Product).offset(i).limit(1))
            product = products.scalars().first()
            if product:
                company = Company(product_id=product.id, **product_data['company'])
                db.add(company)
    
    await db.commit()
    return True 