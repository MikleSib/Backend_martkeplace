from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import UserProfile

async def create_user_profile(db: AsyncSession, user_id: int, full_name: str, phone: str, about_me: str = None, location: str = None):
    profile = UserProfile(
        user_id=user_id,
        full_name=full_name,
        phone=phone,
        about_me=about_me,
        location=location
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile

async def get_user_profile(db: AsyncSession, user_id: int):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    return result.scalar_one_or_none()