from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from database import UserProfile
from database import create_user_profile, get_user_profile
from config import ProfileCreate

router = APIRouter()



@router.post("/user/profile")
async def create_profile(profile_data: ProfileCreate, db: AsyncSession = Depends(get_db)):
    existing_profile = await get_user_profile(db, profile_data.user_id)
    if existing_profile:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    profile = await create_user_profile(
        db=db,
        user_id=profile_data.user_id,
        full_name=profile_data.full_name,
        phone=profile_data.phone,
        about_me=profile_data.about_me,
        location=profile_data.location
    )
    return profile

@router.get("/user/profile/{user_id}")
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    profile = await get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile