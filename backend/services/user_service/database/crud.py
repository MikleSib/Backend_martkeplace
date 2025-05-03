from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from .models import UserProfile

async def create_user_profile(
    db: AsyncSession,
    user_id: int,
    username: str,
    full_name: str,
    about_me: Optional[str] = None,
    avatar: Optional[str] = None,
    signature: Optional[str] = None,
    posts_count: int = 0,
    role: str = "user"
):
    profile = UserProfile(
        user_id=user_id,
        username=username,
        full_name=full_name,
        about_me=about_me,
        avatar=avatar,
        signature=signature,
        posts_count=posts_count,
        role=role
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile

async def get_user_profile(db: AsyncSession, user_id: int):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    return result.scalar_one_or_none()

async def get_user_profiles_by_ids(db: AsyncSession, user_ids: List[int]):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id.in_(user_ids)))
    return result.scalars().all()

async def update_user_profile(
    db: AsyncSession,
    user_id: int,
    full_name: Optional[str] = None,
    about_me: Optional[str] = None,
    avatar: Optional[str] = None,
    signature: Optional[str] = None,
    posts_count: Optional[int] = None,
    role: Optional[str] = None
):
    profile = await get_user_profile(db, user_id)
    if not profile:
        return None
        
    if full_name is not None:
        profile.full_name = full_name
    if about_me is not None:
        profile.about_me = about_me
    if avatar is not None:
        profile.avatar = avatar
    if signature is not None:
        profile.signature = signature
    if posts_count is not None:
        profile.posts_count = posts_count
    if role is not None:
        profile.role = role
        
    await db.commit()
    await db.refresh(profile)
    return profile

async def increment_posts_count(db: AsyncSession, user_id: int, increment: int = 1):
    """Увеличивает счетчик сообщений пользователя"""
    profile = await get_user_profile(db, user_id)
    if not profile:
        return None
    
    profile.posts_count += increment
    await db.commit()
    await db.refresh(profile)
    return profile