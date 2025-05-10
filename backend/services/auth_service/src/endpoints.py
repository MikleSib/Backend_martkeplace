from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, get_user_by_email, get_user_by_username, create_user
from config import UserRegister, UserLogin
from jwt import create_access_token, create_refresh_token, verify_access_token, verify_refresh_token
from src.utils.password import verify_password
import httpx
from pydantic import BaseModel
from fastapi.responses import JSONResponse

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
USER_SERVICE_URL = "http://user_service:8002"

class RefreshToken(BaseModel):
    refresh_token: str

# Добавляем модель для запроса смены пароля
class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class TokenGenerationData(BaseModel):
    email: str
    user_id: int

@router.post("/auth/register")
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Приводим email к нижнему регистру
    user_data.email = user_data.email.lower()
    
    # Сначала проверяем email
    email_user = await get_user_by_email(db, user_data.email)
    if email_user:
        # Добавляем логирование
        print(f"Registration failed: email {user_data.email} already exists")
        # Явно возвращаем JSONResponse с кодом 400
        return JSONResponse(
            status_code=400,
            content={"detail": "Пользователь с такой почтой уже существует"}
        )
    
    # Затем проверяем username
    username_user = await get_user_by_username(db, user_data.username)
    if username_user:
        # Добавляем логирование
        print(f"Registration failed: username {user_data.username} already exists")
        # Явно возвращаем JSONResponse с кодом 400
        return JSONResponse(
            status_code=400,
            content={"detail": "Пользователь с таким именем уже существует"}
        )
    
    # Если конфликтов нет, создаем пользователя
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
    user_data.email = user_data.email.lower()  # Email в нижний регистр
    
    # Ищем пользователя по email вместо username
    user = await get_user_by_email(db, user_data.email)
    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="Неверные учетные данные")
    
    # Проверяем подтверждение email
    if not user.is_email_verified:
        raise HTTPException(status_code=403, detail="Необходимо подтвердить email перед входом в систему")
    
    # Формируем токен, используя username для sub (это обеспечит обратную совместимость)
    access_token = create_access_token({
        "sub": user.username,  # sub остается username для обратной совместимости
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
        return {"valid": False, "message": "Invalid token"}
    
    user = await get_user_by_username(db, payload["sub"])
    if not user:
        return {"valid": False, "message": "User not found"}
        
    return {
        "valid": True,
        "user_id": user.id,
        "is_admin": user.is_admin,
        "username": user.username,
        "email": user.email
    }

@router.post("/auth/change-password")
async def change_password(
    password_data: ChangePassword, 
    token: str, 
    db: AsyncSession = Depends(get_db)
):
    # Проверяем токен
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    
    # Получаем пользователя по username из sub
    user = await get_user_by_username(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем старый пароль
    if not verify_password(password_data.old_password, user.password):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    # Хешируем и устанавливаем новый пароль
    from src.utils.password import get_password_hash
    user.password = get_password_hash(password_data.new_password)
    
    # Сохраняем изменения
    await db.commit()
    
    return {"message": "Пароль успешно изменен"}

@router.post("/auth/verify-email")
async def verify_email(email: str, code: str, db: AsyncSession = Depends(get_db)):
    """
    Подтверждает email пользователя с помощью кода верификации
    """
    try:
        # Приводим email к нижнему регистру
        email = email.lower()
        
        # Находим пользователя по email
        user = await get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Если код "vk_verified", автоматически подтверждаем email
        if code == "vk_verified":
            user.is_email_verified = True
            await db.commit()
            return {
                "message": "Email успешно подтвержден через VK",
                "user_id": user.id,
                "username": user.username,
                "email": user.email
            }
        
        # Для обычной верификации проверка кода будет выполняться на уровне API Gateway через Redis
        user.is_email_verified = True
        await db.commit()
        
        return {
            "message": "Email успешно подтвержден",
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка верификации email: {str(e)}")

@router.post("/auth/check-email")
async def check_email(email: str, db: AsyncSession = Depends(get_db)):
    """
    Проверяет существование пользователя по email и возвращает токены, если пользователь существует
    """
    try:
        # Приводим email к нижнему регистру
        email = email.lower()
        
        # Находим пользователя по email
        user = await get_user_by_email(db, email)
        if not user:
            return JSONResponse(
                status_code=404,
                content={"detail": "Пользователь не найден"}
            )
        
        # Если пользователь найден, создаем токены
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при проверке email: {str(e)}")

@router.post("/auth/generate-tokens")
async def generate_tokens(token_data: TokenGenerationData, db: AsyncSession = Depends(get_db)):
    """
    Генерирует токены для существующего пользователя (используется для социальной авторизации)
    """
    try:
        # Приводим email к нижнему регистру
        email = token_data.email.lower()
        
        # Находим пользователя по email
        user = await get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Создаем токены
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации токенов: {str(e)}")