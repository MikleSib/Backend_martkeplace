from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from database import get_db
from database import PostCRUD
from database import Post
from config import (
    PostCreate, PostUpdate, PostResponse,
    CommentCreate, CommentUpdate, CommentResponse,
    LikeCreate, LikeResponse,
    PostImageCreate, PostImageResponse
)
import requests
import json
from src.utils.telegram_notifications import send_post_notification

router = APIRouter()

# Redis cache helpers
REDIS_SERVICE_URL = "http://redis_service:8003"
POSTS_CACHE_KEY = "all_posts"
CACHE_EXPIRATION = 3600  # 1 hour

async def get_posts_from_cache():
    try:
        response = requests.get(f"{REDIS_SERVICE_URL}/get/{POSTS_CACHE_KEY}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting posts from cache: {e}")
        return None

async def set_posts_in_cache(posts):
    try:
        data = {
            "key": POSTS_CACHE_KEY,
            "value": posts,
            "expire": CACHE_EXPIRATION
        }
        requests.post(f"{REDIS_SERVICE_URL}/set", json=data)
    except Exception as e:
        print(f"Error setting posts in cache: {e}")

async def invalidate_posts_cache():
    try:
        # Устанавливаем пустой кэш с истекшим сроком действия (1 секунда)
        data = {
            "key": POSTS_CACHE_KEY,
            "value": {},
            "expire": 1
        }
        requests.post(f"{REDIS_SERVICE_URL}/set", json=data)
    except Exception as e:
        print(f"Error invalidating posts cache: {e}")

@router.post("/posts/", response_model=PostResponse)
async def create_post(post: PostCreate, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    new_post = await crud.create_post(
        title=post.title,
        content=post.content,
        author_id=post.author_id,
        images=post.images
    )
    # Инвалидируем кэш при создании нового поста
    await invalidate_posts_cache()

    # Отправляем уведомление в Telegram
    try:
        await send_post_notification(
            post_id=new_post.id,
            title=new_post.title,
            content=new_post.content,
            author_id=new_post.author_id
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления в Telegram: {str(e)}")

    return new_post

@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    # Для отдельного поста кэширование не используем, поскольку 
    # это не критическая операция и она уже оптимизирована в базе данных
    crud = PostCRUD(db)
    post = await crud.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.get("/posts/", response_model=dict)
async def get_all_posts(page: int = 1, page_size: int = 2, db: AsyncSession = Depends(get_db)):
    # Конвертируем page в skip
    skip = (page - 1) * page_size
    
    # Получаем данные из БД
    crud = PostCRUD(db)
    total = await crud.get_total_posts_count()
    posts = await crud.get_all_posts(skip=skip, limit=page_size)
    
    # Вычисляем общее количество страниц
    total_pages = (total + page_size - 1) // page_size
    
    # Проверяем, существует ли запрашиваемая страница
    if page > total_pages and total > 0:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Преобразуем посты в словари
    posts_data = []
    for post in posts:
        # Получаем информацию о пользователях для лайков
        likes_data = []
        for like in post.likes:
            user_info = await crud.get_user_info(like.user_id)
            like_dict = {
                "id": like.id,
                "user_id": like.user_id,
                "post_id": post.id,
                "created_at": like.created_at,
                "user": user_info if user_info else {
                    "id": like.user_id,
                    "username": "[Удаленный пользователь]",
                    "full_name": "[Удаленный пользователь]",
                    "about_me": None
                }
            }
            likes_data.append(like_dict)

        # Получаем информацию об авторах комментариев
        comments_data = []
        for comment in post.comments:
            author_info = await crud.get_user_info(comment.author_id)
            comment_dict = {
                "id": comment.id,
                "content": comment.content,
                "author_id": comment.author_id,
                "post_id": post.id,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "author": author_info if author_info else {
                    "id": comment.author_id,
                    "username": "[Удаленный пользователь]",
                    "full_name": "[Удаленный пользователь]",
                    "about_me": None
                }
            }
            comments_data.append(comment_dict)

        post_dict = {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "author_id": post.author_id,
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "images": [{"id": img.id, "image_url": img.image_url, "post_id": img.post_id, "created_at": img.created_at} for img in post.images],
            "comments": comments_data,
            "likes": likes_data
        }
        
        # Добавляем информацию об авторе
        if hasattr(post, 'author_info') and post.author_info:
            post_dict["author"] = post.author_info
        else:
            post_dict["author"] = {
                "id": post.author_id,
                "username": "[Удаленный пользователь]",
                "full_name": "[Удаленный пользователь]",
                "about_me": None
            }
            
        posts_data.append(post_dict)
    
    await set_posts_in_cache(posts_data)
    
    return {
        "items": posts_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.get("/users/{author_id}/posts/", response_model=List[PostResponse])
async def get_user_posts(author_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    return await crud.get_user_posts(author_id=author_id, skip=skip, limit=limit)

@router.patch("/posts/{post_id}", response_model=PostResponse)
async def update_post(post_id: int, post_update: PostUpdate, author_id: int, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    post = await crud.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != author_id:
        raise HTTPException(status_code=403, detail="You don't have permission to update this post")
    
    updated_post = await crud.update_post(
        post_id=post_id,
        title=post_update.title,
        content=post_update.content,
        images=post_update.images
    )
    # Инвалидируем кэш при обновлении поста
    await invalidate_posts_cache()
    return updated_post

@router.delete("/posts/{post_id}")
async def delete_post(post_id: int, admin_id: str, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    post = await crud.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    try:
        response = requests.get(
            f"http://auth_service:8001/auth/check_token",
            params={"token": admin_id} 
        )
        if not response.json() or not response.json().get("is_admin", False):
            raise HTTPException(status_code=403, detail="Only administrators can delete posts")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    success = await crud.delete_post(post_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete post")
    
    # Инвалидируем кэш при удалении поста
    await invalidate_posts_cache()
    return {"message": "Post deleted successfully"}


@router.post("/posts/{post_id}/comments/", response_model=CommentResponse)
async def create_comment(
    post_id: int,
    comment: CommentCreate,
    db: AsyncSession = Depends(get_db)
):
    crud = PostCRUD(db)
    new_comment = await crud.create_comment(
        post_id=post_id,
        content=comment.content,
        author_id=comment.author_id
    )
    if not new_comment:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Инвалидируем кэш при добавлении комментария
    await invalidate_posts_cache()
    return new_comment

@router.get("/posts/{post_id}/comments/", response_model=List[CommentResponse])
async def get_post_comments(
    post_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    crud = PostCRUD(db)
    return await crud.get_post_comments(post_id=post_id, skip=skip, limit=limit)

@router.patch("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    author_id: int,
    db: AsyncSession = Depends(get_db)
):
    crud = PostCRUD(db)
    comment = await crud.get_comment(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != author_id:
        raise HTTPException(status_code=403, detail="You don't have permission to update this comment")
    
    updated_comment = await crud.update_comment(
        comment_id=comment_id,
        content=comment_update.content
    )
    
    # Инвалидируем кэш при обновлении комментария
    await invalidate_posts_cache()
    return updated_comment

@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    admin_id: str,
    db: AsyncSession = Depends(get_db)
):
    crud = PostCRUD(db)
    comment = await crud.get_comment(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    
    success = await crud.delete_comment(comment_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete comment")
    
    # Инвалидируем кэш при удалении комментария
    await invalidate_posts_cache()
    return {"message": "Comment deleted successfully"}


@router.post("/posts/{post_id}/likes/", response_model=LikeResponse)
async def add_like(
    post_id: int,
    like: LikeCreate,
    db: AsyncSession = Depends(get_db)
):
    crud = PostCRUD(db)
    new_like = await crud.add_like(
        post_id=post_id,
        user_id=like.user_id
    )
    if not new_like:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Инвалидируем кэш при добавлении лайка
    await invalidate_posts_cache()
    return new_like

@router.delete("/posts/{post_id}/likes/{user_id}")
async def remove_like(
    post_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    crud = PostCRUD(db)
    success = await crud.remove_like(post_id=post_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Like not found")
    
    # Инвалидируем кэш при удалении лайка
    await invalidate_posts_cache()
    return {"message": "Like removed successfully"}
