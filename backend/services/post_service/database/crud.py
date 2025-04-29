from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from .models import Post

class PostCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_post(self, title: str, content: str, author_id: int) -> Post:
        post = Post(
            title=title,
            content=content,
            author_id=author_id
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def get_post(self, post_id: int) -> Optional[Post]:
        result = await self.session.execute(
            select(Post).where(Post.id == post_id)
        )
        return result.scalar_one_or_none()

    async def get_all_posts(self, skip: int = 0, limit: int = 100) -> List[Post]:
        result = await self.session.execute(
            select(Post)
            .offset(skip)
            .limit(limit)
            .order_by(Post.created_at.desc())
        )
        return result.scalars().all()

    async def get_user_posts(self, author_id: int, skip: int = 0, limit: int = 100) -> List[Post]:
        result = await self.session.execute(
            select(Post)
            .where(Post.author_id == author_id)
            .offset(skip)
            .limit(limit)
            .order_by(Post.created_at.desc())
        )
        return result.scalars().all()

    async def update_post(self, post_id: int, title: Optional[str] = None, content: Optional[str] = None) -> Optional[Post]:
        post = await self.get_post(post_id)
        if not post:
            return None

        if title is not None:
            post.title = title
        if content is not None:
            post.content = content

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