from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict
from . import models, schemas, database
from datetime import datetime
from .init_db import init_db

app = FastAPI(
    title="News Service",
    description="Service for managing news and guides",
    version="1.0.0"
)

# Инициализация базы данных при запуске
init_db()

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/news/", response_model=models.News)
def create_news(news: models.NewsCreate, author_id: int, db: Session = Depends(get_db)):
    db_news = schemas.NewsDB(
        title=news.title,
        category=news.category,
        author_id=author_id,
        contents=[
            schemas.NewsContentDB(
                type=content.type,
                content=content.content,
                order=content.order
            ) for content in news.contents
        ]
    )
    db.add(db_news)
    db.commit()
    db.refresh(db_news)
    return db_news

@app.get("/news/", response_model=List[models.News])
def get_news(
    skip: int = 0,
    limit: int = 100,
    category: models.NewsCategory = None,
    db: Session = Depends(get_db)
):
    query = db.query(schemas.NewsDB)
    if category:
        query = query.filter(schemas.NewsDB.category == category)
    return query.offset(skip).limit(limit).all()

@app.get("/news/{news_id}", response_model=models.News)
def get_news_by_id(news_id: int, db: Session = Depends(get_db)):
    news = db.query(schemas.NewsDB).filter(schemas.NewsDB.id == news_id).first()
    if news is None:
        raise HTTPException(status_code=404, detail="News not found")
    return news

@app.patch("/news/{news_id}", response_model=models.News)
def update_news(
    news_id: int,
    news_update: models.NewsUpdate,
    author_id: int,
    db: Session = Depends(get_db)
):
    db_news = db.query(schemas.NewsDB).filter(schemas.NewsDB.id == news_id).first()
    if db_news is None:
        raise HTTPException(status_code=404, detail="News not found")
    if db_news.author_id != author_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this news")

    # Обновляем основные поля
    for key, value in news_update.dict(exclude={'contents'}).items():
        setattr(db_news, key, value)

    # Удаляем старые контенты
    db.query(schemas.NewsContentDB).filter(schemas.NewsContentDB.news_id == news_id).delete()

    # Добавляем новые контенты
    for content in news_update.contents:
        db_content = schemas.NewsContentDB(
            news_id=news_id,
            type=content.type,
            content=content.content,
            order=content.order
        )
        db.add(db_content)

    db.commit()
    db.refresh(db_news)
    return db_news

@app.delete("/news/{news_id}")
def delete_news(news_id: int, author_id: int, db: Session = Depends(get_db)):
    db_news = db.query(schemas.NewsDB).filter(schemas.NewsDB.id == news_id).first()
    if db_news is None:
        raise HTTPException(status_code=404, detail="News not found")
    if db_news.author_id != author_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this news")

    db.delete(db_news)
    db.commit()
    return {"message": "News deleted successfully"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/news/stats/categories", response_model=Dict[str, int])
def get_news_categories_stats(db: Session = Depends(get_db)):
    """
    Получить количество новостей в каждой категории
    """
    try:
        # Получаем статистику по категориям
        stats = db.query(
            schemas.NewsDB.category,
            func.count(schemas.NewsDB.id).label('count')
        ).group_by(schemas.NewsDB.category).all()
        
        # Преобразуем результат в словарь
        result = {category.value: 0 for category in models.NewsCategory}  # Инициализируем все категории нулями
        for category, count in stats:
            result[category] = count
            
        return result
    except Exception as e:
        logger.error(f"Error getting news categories stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 