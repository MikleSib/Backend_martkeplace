from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from .models import UserProfile

async def create_user_profile(db: AsyncSession, user_id: int, username: str, full_name: str, about_me: Optional[str] = None):
    profile = UserProfile(
        user_id=user_id,
        username=username,
        full_name=full_name,
        about_me=about_me
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile

async def get_user_profile(db: AsyncSession, user_id: int):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    return result.scalar_one_or_none()

async def update_user_profile(db: AsyncSession, user_id: int, full_name: Optional[str] = None, about_me: Optional[str] = None):
    profile = await get_user_profile(db, user_id)
    if not profile:
        return None
        
    if full_name is not None:
        profile.full_name = full_name
    if about_me is not None:
        profile.about_me = about_me
        
    await db.commit()
    await db.refresh(profile)
    return profile