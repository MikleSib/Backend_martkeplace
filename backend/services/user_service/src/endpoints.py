from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from database import UserProfile
from database import create_user_profile, get_user_profile
from config import ProfileCreate

router = APIRouter()



@router.post("/user/profile")
async def create_profile(profile_data: ProfileCreate, db: AsyncSession = Depends(get_db)):
    try:
        
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == profile_data.user_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Profile already exists")
        
        
        profile = UserProfile(
            user_id=profile_data.user_id,
            username=profile_data.username,
            full_name=profile_data.full_name,
            about_me=profile_data.about_me
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/profile/{user_id}")
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    profile = await get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
