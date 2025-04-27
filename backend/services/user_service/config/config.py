from pydantic import BaseModel

class ProfileCreate(BaseModel):
    user_id: int
    full_name: str
    phone: str
    about_me: str | None = None
    location: str | None = None
