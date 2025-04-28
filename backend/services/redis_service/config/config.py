from pydantic import BaseModel

class CacheSet(BaseModel):
    key: str
    value: dict
    expire: int = 300
