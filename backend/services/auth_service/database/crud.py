from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User
from src.utils.password import get_password_hash

async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()

async def create_user(db: AsyncSession, username: str, password: str, email: str):
    hashed_password = get_password_hash(password)
    user = User(username=username, password=hashed_password, email=email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user