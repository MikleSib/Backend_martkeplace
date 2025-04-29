from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from database import get_db
from database import PostCRUD
from database import Post
from config import PostCreate, PostUpdate, PostResponse

router = APIRouter()


@router.post("/posts/", response_model=PostResponse)
async def create_post(post: PostCreate, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    return await crud.create_post(
        title=post.title,
        content=post.content,
        author_id=post.author_id
    )

@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    post = await crud.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.get("/posts/", response_model=List[PostResponse])
async def get_all_posts(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    return await crud.get_all_posts(skip=skip, limit=limit)

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
        content=post_update.content
    )
    return updated_post
