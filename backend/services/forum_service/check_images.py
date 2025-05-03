import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models import Image, Post

# Параметры соединения с базой данных
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@postgres:5432/forum_db"

async def check_images():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Проверяем таблицу с изображениями
        query = select(Image)
        result = await session.execute(query)
        images = result.scalars().all()
        
        print(f"Всего найдено {len(images)} изображений:")
        for img in images:
            print(f"ID: {img.id}, Post ID: {img.post_id}, URL: {img.image_url}")
        
        # Проверяем посты с изображениями
        posts_query = select(Post).where(Post.id.in_([img.post_id for img in images]))
        posts_result = await session.execute(posts_query)
        posts = posts_result.scalars().all()
        
        print(f"\nНайдено {len(posts)} постов с изображениями:")
        for post in posts:
            print(f"Post ID: {post.id}, Author ID: {post.author_id}, Content: {post.content[:50]}...")

if __name__ == "__main__":
    asyncio.run(check_images()) 