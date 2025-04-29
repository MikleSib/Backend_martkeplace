from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class PostImageBase(BaseModel):
    image_url: str

class PostImageCreate(PostImageBase):
    pass

class PostImageResponse(PostImageBase):
    id: int
    post_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    author_id: int

class CommentUpdate(BaseModel):
    content: Optional[str] = None

class CommentResponse(CommentBase):
    id: int
    post_id: int
    author_id: int
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
    created_at: datetime

    class Config:
        from_attributes = True

class PostBase(BaseModel):
    title: str
    content: str  # HTML контент с форматированием

class PostCreate(PostBase):
    author_id: int
    images: Optional[List[PostImageCreate]] = None

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[PostImageCreate]] = None

class PostResponse(PostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    images: List[PostImageResponse] = []
    comments: List[CommentResponse] = []
    likes: List[LikeResponse] = []

    class Config:
        from_attributes = True