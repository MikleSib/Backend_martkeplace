from pydantic import BaseModel
from typing import Union, List, Dict, Any

class CacheSet(BaseModel):
    key: str
    value: Union[Dict[str, Any], List[Dict[str, Any]], Any]
    expire: int = 300
