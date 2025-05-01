from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict
import requests
from .models import Post, PostImage, Comment, Like

USER_SERVICE_URL = "http://user_service:8002"

class PostCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_info(self, user_id: int) -> Optional[Dict]:
        try:
            response = requests.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None

    async def create_post(self, title: str, content: str, author_id: int, images: Optional[List[dict]] = None) -> Post:
        post = Post(
            title=title,
            content=content,
            author_id=author_id
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)

        if images:
            for image in images:
                post_image = PostImage(
                    post_id=post.id,
                    image_url=image.image_url
                )
                self.session.add(post_image)
            await self.session.commit()

        result = await self.session.execute(
            select(Post)
            .options(
                selectinload(Post.images),
                selectinload(Post.comments),
                selectinload(Post.likes)
            )
            .where(Post.id == post.id)
        )
        post = result.scalar_one_or_none()
        
        author_info = await self.get_user_info(post.author_id)
        if author_info:
            post.author_info = author_info
            
        return post

    async def get_post(self, post_id: int) -> Optional[Post]:
        result = await self.session.execute(
            select(Post)
            .options(
                selectinload(Post.images),
                selectinload(Post.comments),
                selectinload(Post.likes)
            )
            .where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        if post:
            author_info = await self.get_user_info(post.author_id)
            if author_info:
                post.author_info = author_info
                
            # Получаем информацию об авторах комментариев
            for comment in post.comments:
                author_info = await self.get_user_info(comment.author_id)
                if author_info:
                    comment.author_info = author_info
                    
            # Получаем информацию о пользователях в лайках
            for like in post.likes:
                user_info = await self.get_user_info(like.user_id)
                if user_info:
                    like.user_info = user_info
                    
        return post

    async def get_all_posts(self, skip: int = 0, limit: int = 100) -> List[Post]:
        result = await self.session.execute(
            select(Post)
            .options(
                selectinload(Post.images),
                selectinload(Post.comments),
                selectinload(Post.likes)
            )
            .offset(skip)
            .limit(limit)
            .order_by(Post.created_at.desc())
        )
        posts = result.scalars().all()
        
        for post in posts:
            author_info = await self.get_user_info(post.author_id)
            if author_info:
                post.author_info = author_info
                
            for comment in post.comments:
                author_info = await self.get_user_info(comment.author_id)
                if author_info:
                    comment.author_info = author_info
                    
            for like in post.likes:
                user_info = await self.get_user_info(like.user_id)
                if user_info:
                    like.user_info = user_info
                    
        return posts

    async def get_user_posts(self, author_id: int, skip: int = 0, limit: int = 100) -> List[Post]:
        result = await self.session.execute(
            select(Post)
            .where(Post.author_id == author_id)
            .options(
                selectinload(Post.images),
                selectinload(Post.comments),
                selectinload(Post.likes)
            )
            .offset(skip)
            .limit(limit)
            .order_by(Post.created_at.desc())
        )
        posts = result.scalars().all()
        
        # Получаем информацию об авторах
        for post in posts:
            author_info = await self.get_user_info(post.author_id)
            if author_info:
                post.author_info = author_info
                
            # Получаем информацию о пользователях в комментариях
            for comment in post.comments:
                author_info = await self.get_user_info(comment.author_id)
                if author_info:
                    comment.author_info = author_info
                    
            # Получаем информацию о пользователях в лайках
            for like in post.likes:
                user_info = await self.get_user_info(like.user_id)
                if user_info:
                    like.user_info = user_info
                    
        return posts

    async def update_post(self, post_id: int, title: Optional[str] = None, content: Optional[str] = None, images: Optional[List[dict]] = None) -> Optional[Post]:
        post = await self.get_post(post_id)
        if not post:
            return None

        if title is not None:
            post.title = title
        if content is not None:
            post.content = content

        if images is not None:
            # Удаляем старые изображения
            await self.session.execute(
                delete(PostImage).where(PostImage.post_id == post_id)
            )
            # Добавляем новые изображения
            for image in images:
                post_image = PostImage(
                    post_id=post.id,
                    image_url=image["image_url"]
                )
                self.session.add(post_image)

        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def delete_post(self, post_id: int) -> bool:
        post = await self.get_post(post_id)
        if not post:
            return False

        await self.session.delete(post)
        await self.session.commit()
        return True

    # Методы для работы с комментариями
    async def create_comment(self, post_id: int, content: str, author_id: int) -> Optional[Comment]:
        post = await self.get_post(post_id)
        if not post:
            return None

        comment = Comment(
            post_id=post_id,
            content=content,
            author_id=author_id
        )
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        
        # Получаем информацию об авторе комментария
        author_info = await self.get_user_info(comment.author_id)
        if author_info:
            comment.author_info = author_info
            
        return comment

    async def get_post_comments(self, post_id: int, skip: int = 0, limit: int = 100) -> List[Comment]:
        result = await self.session.execute(
            select(Comment)
            .where(Comment.post_id == post_id)
            .offset(skip)
            .limit(limit)
            .order_by(Comment.created_at.desc())
        )
        comments = result.scalars().all()
        
        # Получаем информацию об авторах комментариев
        for comment in comments:
            author_info = await self.get_user_info(comment.author_id)
            if author_info:
                comment.author_info = author_info
                
        return comments

    async def update_comment(self, comment_id: int, content: str) -> Optional[Comment]:
        result = await self.session.execute(
            select(Comment).where(Comment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        if not comment:
            return None

        comment.content = content
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def get_comment(self, comment_id: int) -> Optional[Comment]:
        result = await self.session.execute(
            select(Comment).where(Comment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        if comment:
            author_info = await self.get_user_info(comment.author_id)
            if author_info:
                comment.author_info = author_info
        return comment

    async def delete_comment(self, comment_id: int) -> bool:
        comment = await self.get_comment(comment_id)
        if not comment:
            return False

        await self.session.delete(comment)
        await self.session.commit()
        return True

    # Методы для работы с лайками
    async def add_like(self, post_id: int, user_id: int) -> Optional[Like]:
        post = await self.get_post(post_id)
        if not post:
            return None

        # Проверяем, не лайкнул ли уже пользователь
        result = await self.session.execute(
            select(Like)
            .where(Like.post_id == post_id)
            .where(Like.user_id == user_id)
        )
        existing_like = result.scalar_one_or_none()
        if existing_like:
            return existing_like

        like = Like(
            post_id=post_id,
            user_id=user_id
        )
        self.session.add(like)
        await self.session.commit()
        await self.session.refresh(like)
        
        # Получаем информацию о пользователе
        user_info = await self.get_user_info(like.user_id)
        if user_info:
            like.user_info = user_info
            
        return like

    async def remove_like(self, post_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(Like)
            .where(Like.post_id == post_id)
            .where(Like.user_id == user_id)
        )
        like = result.scalar_one_or_none()
        if not like:
            return False

        await self.session.delete(like)
        await self.session.commit()
        return True 