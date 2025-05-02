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

router = APIRouter()


@router.post("/posts/", response_model=PostResponse)
async def create_post(post: PostCreate, db: AsyncSession = Depends(get_db)):
    crud = PostCRUD(db)
    return await crud.create_post(
        title=post.title,
        content=post.content,
        author_id=post.author_id,
        images=post.images
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
        content=post_update.content,
        images=post_update.images
    )
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
    return {"message": "Like removed successfully"}
