from pydantic import BaseModel

class ProfileCreate(BaseModel):
    user_id: int
    username: str
    full_name: str
    about_me: str | None = None
