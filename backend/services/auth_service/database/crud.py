from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User
from src.utils.password import get_password_hash

async def get_user_by_email(db: AsyncSession, email: str):
    """Получение пользователя по email (приведенному к нижнему регистру)"""
    email = email.lower()  # Приводим email к нижнему регистру
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def get_user_by_username(db: AsyncSession, username: str):
    """Получение пользователя по username"""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()

async def create_user(db: AsyncSession, username: str, password: str, email: str, is_admin: bool = False):
    """Создание пользователя с email в нижнем регистре"""
    hashed_password = get_password_hash(password)
    email = email.lower()  # Приводим email к нижнему регистру
    user = User(username=username, password=hashed_password, email=email, is_admin=is_admin)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user