from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False)
    old_price = Column(Float, nullable=True)
    discount = Column(Integer, nullable=True)
    image = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    brand = Column(String(50), nullable=True, index=True)
    status = Column(String(20), nullable=False)
    rating = Column(Float, nullable=False)
    external_url = Column(String(255), nullable=False)
    store = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(String, default=datetime.utcnow)
    updated_at = Column(String, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="products", cascade="all, delete-orphan", uselist=False)

    # Создаем индексы для часто используемых полей при поиске и фильтрации
    __table_args__ = (
        Index('idx_title_category_brand', 'title', 'category', 'brand'),
        Index('idx_store_status', 'store', 'status'),
        Index('idx_price', 'price'),
    )

    def __repr__(self):
        return f"<Product {self.title}>"


class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='CASCADE'))
    name = Column(String(100), nullable=False)
    rating = Column(Float, nullable=False)
    products_count = Column(Integer, nullable=False)
    is_premium = Column(Boolean, nullable=True)
    has_ozon_delivery = Column(Boolean, nullable=True)
    return_period = Column(Integer, nullable=True)
    
    products = relationship("Product", back_populates="company") 