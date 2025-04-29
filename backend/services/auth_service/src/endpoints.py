from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from database import get_user_by_username, create_user
from config import UserRegister, UserLogin
from jwt import create_access_token, create_refresh_token, verify_access_token
import httpx

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
USER_SERVICE_URL = "http://user_service:8002"

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
    if not user or user.password != user_data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    access_token = create_access_token({"sub": user.username, "email": user.email, "id": user.id})
    refresh_token = create_refresh_token({"sub": user.username, "email": user.email, "id": user.id})
    return {"access_token": access_token, "refresh_token": refresh_token}

@router.post("/auth/refresh")
async def refresh(refresh_token: str = Depends(oauth2_scheme)):
    payload = verify_access_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token = create_access_token({"sub": payload["sub"], "email": payload["email"], "id": payload["id"]})
    return {"access_token": access_token}

@router.get("/auth/check_token")
async def check_token(token: str):
    payload = verify_access_token(token)
    if not payload:
        return False   
    return {"user_id": payload["id"]}