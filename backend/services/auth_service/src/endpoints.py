from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from database import get_user_by_username, create_user
from config import UserRegister, UserLogin
from jwt import create_access_token, create_refresh_token, verify_access_token, verify_refresh_token
from src.utils.password import verify_password
import httpx
from pydantic import BaseModel

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
USER_SERVICE_URL = "http://user_service:8002"

class RefreshToken(BaseModel):
    refresh_token: str

@router.post("/auth/register")
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(db, user_data.username)
    if user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user = await create_user(db, user_data.username, user_data.password, user_data.email)
    async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{USER_SERVICE_URL}/user/profile",
                    json={
                        "user_id": user.id,
                        "username": user_data.username,
                        "full_name": user_data.full_name,
                        "about_me": user_data.about_me
                    }
                )
                if response.status_code != 200:
                    await db.delete(user)
                    await db.commit()
                    raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Failed to create user profile"))
            except httpx.HTTPError as e:
                await db.delete(user)
                await db.commit()
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(status_code=500, detail="Failed to create user profile")

    return {"id": user.id, "username": user.username, "email": user.email}

@router.post("/auth/login")
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(db, user_data.username)
    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    access_token = create_access_token({
        "sub": user.username, 
        "email": user.email, 
        "id": user.id,
        "is_admin": user.is_admin
    })
    refresh_token = create_refresh_token({
        "sub": user.username, 
        "email": user.email, 
        "id": user.id,
        "is_admin": user.is_admin
    })
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        }
    }

@router.post("/auth/refresh")
async def refresh(refresh_data: RefreshToken):
    payload = verify_refresh_token(refresh_data.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    access_token = create_access_token({
        "sub": payload["sub"], 
        "email": payload["email"], 
        "id": payload["id"],
        "is_admin": payload.get("is_admin", False)
    })
    
    # Создаем новый refresh токен
    refresh_token = create_refresh_token({
        "sub": payload["sub"], 
        "email": payload["email"], 
        "id": payload["id"],
        "is_admin": payload.get("is_admin", False)
    })
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }

@router.get("/auth/check_token")
async def check_token(token: str, db: AsyncSession = Depends(get_db)):
    payload = verify_access_token(token)
    if not payload:
        return False
    
    user = await get_user_by_username(db, payload["sub"])
    if not user:
        return False
        
    return {
        "user_id": user.id,
        "is_admin": user.is_admin
    }