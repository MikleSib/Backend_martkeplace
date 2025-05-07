from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any

class CompanyBase(BaseModel):
    name: str
    rating: float
    products_count: int
    is_premium: Optional[bool] = None
    has_ozon_delivery: Optional[bool] = None
    return_period: Optional[int] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: int
    product_id: int
    
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    title: str = Field(..., max_length=100)
    price: float
    old_price: Optional[float] = None
    discount: Optional[int] = None
    image: HttpUrl
    category: str
    brand: Optional[str] = None
    status: str = Field(..., pattern="^(in-stock|out-of-stock|sale)$")
    rating: float = Field(..., ge=0, le=5)
    external_url: HttpUrl
    store: str = Field(..., pattern="^(ozon|wildberries|aliexpress|other)$")
    description: Optional[str] = None

class ProductCreate(ProductBase):
    company: Optional[CompanyBase] = None

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    price: Optional[float] = None
    old_price: Optional[float] = None
    discount: Optional[int] = None
    image: Optional[HttpUrl] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(in-stock|out-of-stock|sale)$")
    rating: Optional[float] = Field(None, ge=0, le=5)
    external_url: Optional[HttpUrl] = None
    store: Optional[str] = Field(None, pattern="^(ozon|wildberries|aliexpress|other)$")
    description: Optional[str] = None
    company: Optional[CompanyBase] = None

class ProductResponse(ProductBase):
    id: int
    company: Optional[CompanyResponse] = None
    
    class Config:
        from_attributes = True

class ProductsListResponse(BaseModel):
    total: int
    page: int
    limit: int
    products: List[ProductResponse] 