from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    id: int
    username: str
    full_name: str
    about_me: Optional[str] = None
    avatar: Optional[str] = None

class UserRegister(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str
    about_me: Optional[str] = None
    is_email_verified: Optional[bool] = False

class UserLogin(BaseModel):
    username: str
    password: str

class PostImageBase(BaseModel):
    image_url: str

class PostImageCreate(BaseModel):
    image_url: str

    class Config:
        from_attributes = True

class PostImageResponse(PostImageBase):
    id: int
    post_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: Optional[str] = None

class CommentResponse(CommentBase):
    id: int
    post_id: int
    author_id: int
    author: UserBase
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LikeBase(BaseModel):
    user_id: int

class LikeCreate(LikeBase):
    pass

class LikeResponse(LikeBase):
    id: int
    post_id: int
    user: UserBase
    created_at: datetime

    class Config:
        from_attributes = True

class PostBase(BaseModel):
    title: str
    content: str 

class PostCreate(PostBase):
    images: Optional[List[PostImageCreate]] = []

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[PostImageCreate]] = None

class PostResponse(PostBase):
    id: int
    author_id: int
    author: UserBase
    created_at: datetime
    updated_at: datetime
    images: List[PostImageResponse] = []
    comments: List[CommentResponse] = []
    likes: List[LikeResponse] = []

    class Config:
        from_attributes = True 