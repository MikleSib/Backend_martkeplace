from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
from .models import NewsCategory, NewsContentType

class NewsContentDB(Base):
    __tablename__ = "news_contents"

    id = Column(Integer, primary_key=True, index=True)
    news_id = Column(Integer, ForeignKey("news.id"))
    type = Column(SQLEnum(NewsContentType))
    content = Column(String)
    order = Column(Integer)

    news = relationship("NewsDB", back_populates="contents")

class NewsDB(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(SQLEnum(NewsCategory))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author_id = Column(Integer)

    contents = relationship("NewsContentDB", back_populates="news", cascade="all, delete-orphan") 