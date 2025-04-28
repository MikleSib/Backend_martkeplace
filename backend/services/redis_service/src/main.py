from fastapi import FastAPI, HTTPException
from config import CacheSet
import redis
import json

app = FastAPI()

redis_client = redis.StrictRedis(host="redis", port=6379, db=0, decode_responses=True)


@app.post("/set")
def set_cache(data: CacheSet):
    redis_client.setex(data.key, data.expire, json.dumps(data.value))
    return {"status": "ok"}

@app.get("/get/{key}")
def get_cache(key: str):
    value = redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Not found")
    return json.loads(value)