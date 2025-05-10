from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from database import UserProfile
from database import create_user_profile, get_user_profile
from config import ProfileCreate, ProfileResponse, UserRole
from typing import List, Optional
from datetime import datetime

router = APIRouter()

@router.post("/user/profile", response_model=ProfileResponse)
async def create_profile(profile_data: ProfileCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Проверяем существует ли уже профиль с таким user_id
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == profile_data.user_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Profile already exists")
        
        # Проверяем уникальность username
        username_check = await db.execute(
            select(UserProfile).where(UserProfile.username == profile_data.username)
        )
        if username_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
        
        # Упрощаем создание профиля, убираем использование enum
        profile = UserProfile(
            user_id=profile_data.user_id,
            username=profile_data.username,
            full_name=profile_data.full_name,
            about_me=profile_data.about_me,
            avatar=profile_data.avatar,
            signature=profile_data.signature,
            registration_date=datetime.utcnow(),
            posts_count=profile_data.posts_count
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

@router.get("/user/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    profile = await get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

# Добавляем альтернативный маршрут для совместимости с запросами форума
@router.get("/users/{user_id}", response_model=ProfileResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Альтернативный маршрут для получения профиля пользователя по ID"""
    return await get_profile(user_id, db)

@router.patch("/user/profile/{user_id}", response_model=ProfileResponse)
async def update_profile(user_id: int, profile_data: ProfileCreate, db: AsyncSession = Depends(get_db)):
    try:
        profile = await get_user_profile(db, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Обновляем только предоставленные поля
        if profile_data.username:
            profile.username = profile_data.username
        if profile_data.full_name:
            profile.full_name = profile_data.full_name
        if profile_data.about_me is not None:
            profile.about_me = profile_data.about_me
        if profile_data.avatar is not None:
            profile.avatar = profile_data.avatar
        if profile_data.signature is not None:
            profile.signature = profile_data.signature
        if profile_data.posts_count is not None:
            profile.posts_count = profile_data.posts_count
        if profile_data.role:
            # Устанавливаем роль через строковое значение
            profile.role = profile_data.role.value
        
        await db.commit()
        await db.refresh(profile)
        return profile
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/batch", response_model=List[ProfileResponse])
async def get_users_batch_get(user_ids: List[int] = Query(None), db: AsyncSession = Depends(get_db)):
    """Получение информации о нескольких пользователях по их ID через параметры запроса"""
    if not user_ids:
        raise HTTPException(status_code=400, detail="Список ID пользователей не может быть пустым")
    
    try:
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id.in_(user_ids))
        )
        profiles = result.scalars().all()
        return profiles
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/batch", response_model=List[ProfileResponse])
async def get_users_batch_post(request_data: dict, db: AsyncSession = Depends(get_db)):
    """Получение информации о нескольких пользователях по их ID через тело запроса"""
    user_ids = request_data.get("user_ids", [])
    if not user_ids:
        raise HTTPException(status_code=400, detail="Список ID пользователей не может быть пустым")
    
    try:
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id.in_(user_ids))
        )
        profiles = result.scalars().all()
        return profiles
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/user/avatar", response_model=ProfileResponse)
async def update_user_avatar(user_id: int, file_url: str, db: AsyncSession = Depends(get_db)):
    """Обновляет аватар пользователя"""
    try:
        # Проверяем существование профиля
        profile = await get_user_profile(db, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        # Обновляем только URL аватара
        profile.avatar = file_url
        
        await db.commit()
        await db.refresh(profile)
        return profile
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/user/avatar/delete", response_model=ProfileResponse)
async def delete_user_avatar(user_id: int, db: AsyncSession = Depends(get_db)):
    """Удаляет аватар пользователя"""
    try:
        profile = await get_user_profile(db, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        profile.avatar = None
        
        await db.commit()
        await db.refresh(profile)
        return profile
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/user/profile/update", response_model=ProfileResponse)
async def update_user_info(
    user_id: int, 
    username: str, 
    about_me: Optional[str] = None, 
    db: AsyncSession = Depends(get_db)
):
    """Обновляет информацию о пользователе (username и about_me)"""
    try:
        profile = await get_user_profile(db, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        # Проверяем уникальность username, если он изменился
        if username != profile.username:
            result = await db.execute(
                select(UserProfile).where(UserProfile.username == username)
            )
            existing_user = result.scalar_one_or_none()
            if existing_user:
                raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
        
        profile.username = username
        if about_me is not None:
            profile.about_me = about_me
        
        await db.commit()
        await db.refresh(profile)
        return profile
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/profile/me", response_model=ProfileResponse)
async def get_my_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получение профиля текущего пользователя по ID из JWT токена"""
    profile = await get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    return profile

@router.post("/user/avatar/vk", response_model=ProfileResponse)
async def update_vk_avatar(user_id: int, avatar_url: str, db: AsyncSession = Depends(get_db)):
    """Обновляет аватар пользователя при VK авторизации без проверки JWT токена"""
    try:
        profile = await get_user_profile(db, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        profile.avatar = avatar_url
        await db.commit()
        await db.refresh(profile)
        return profile
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
