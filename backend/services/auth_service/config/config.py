from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegister(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str
    about_me: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class VKAuth(BaseModel):
    vk_id: int
    email: str
    first_name: str
    last_name: str
    photo_url: Optional[str] = None
