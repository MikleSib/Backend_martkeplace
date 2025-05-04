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
