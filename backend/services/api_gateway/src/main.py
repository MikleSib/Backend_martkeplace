import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
from .config import UserRegister, UserLogin, PostCreate, PostUpdate, PostResponse
import logging

app = FastAPI(
    title="API Gateway",
    description="API Gateway for microservices",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Добавляем схему безопасности для Swagger
security = HTTPBearer()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = "http://auth_service:8001"
USER_SERVICE_URL = "http://user_service:8002"
REDIS_SERVICE_URL = "http://redis_service:8003"
POST_SERVICE_URL = "http://post_service:8004"

SERVICE_URLS = {
    "auth": AUTH_SERVICE_URL,
    "user": USER_SERVICE_URL,
    "redis": REDIS_SERVICE_URL,
    "post": POST_SERVICE_URL
}

def get_from_cache(key):
    resp = requests.get(f"{REDIS_SERVICE_URL}/get/{key}")
    if resp.status_code == 200:
        return resp.json()
    return None

def set_to_cache(key, value, expire=300):
    requests.post(f"{REDIS_SERVICE_URL}/set", json={"key": key, "value": value, "expire": expire})

def check_route_enabled(route: str) -> bool:
    try:
        logger.info(f"Checking route: {route}")
        service_name = None
        for name, url in SERVICE_URLS.items():
            if url in route:
                service_name = name
                break
                
        if not service_name:
            logger.warning(f"No service found for route: {route}")
            return False
            
        service_base_url = SERVICE_URLS[service_name]
        logger.info(f"Checking health endpoint for service {service_name} at {service_base_url}/health")
        response = requests.get(f"{service_base_url}/health")
        is_healthy = response.status_code == 200
        logger.info(f"Service {service_name} health check result: {'healthy' if is_healthy else 'unhealthy'}")
        return is_healthy
    except requests.RequestException as e:
        logger.error(f"Request failed for route {route}: {str(e)}")
        return False

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if not response.json():
            raise HTTPException(status_code=401, detail="Invalid token")
        return response.json()["user_id"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
async def root():
    return {"message": "health check"}

@app.post("/auth/register")
async def register(user_data: UserRegister):
    if not check_route_enabled(f"{AUTH_SERVICE_URL}/auth/register"):
        return {"message": "auth service is not running"}
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/register",
            json=user_data.dict()
        )
        return response.json()
    except ValueError as e:
        return {
            "error": "Invalid JSON format",
        }
    except Exception as e:
        return {"error": "Internal server error"}

@app.post("/auth/login")
async def login(user_data: UserLogin):
    if not check_route_enabled(f"{AUTH_SERVICE_URL}/auth/login"):
        return {"message": "auth service is not running"}
    try:     
        response = requests.post(f"{AUTH_SERVICE_URL}/auth/login", json=user_data.dict())
        return response.json()
    except ValueError as e:
        return {"error": "Invalid JSON format"}
    except Exception as e:
        return {"error": "Internal server error"}

@app.get("/user/get_profile")
async def get_profile(user_id: int):
    if not check_route_enabled(f"{USER_SERVICE_URL}/user/profile"):
        return {"message": "user service is not running"}
    
    cache_key = f"user_profile_{user_id}"
    cached_profile = get_from_cache(cache_key)
    if cached_profile:
        logger.info(f"Profile for user {user_id} found in cache")
        return cached_profile

    try:
        response = requests.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
        profile_data = response.json()
        
        set_to_cache(cache_key, profile_data)
        logger.info(f"Profile for user {user_id} saved to cache")
        
        return profile_data
    except Exception as e:
        logger.error(f"Error getting profile for user {user_id}: {str(e)}")
        return {"error": "Internal server error"}

@app.post("/post/create", response_model=PostResponse)
async def create_post(post_data: PostCreate, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.post(
            f"{POST_SERVICE_URL}/posts/",
            json={**post_data.dict(), "author_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error creating post"))
        return PostResponse(**response.json())
    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/post/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/post/{post_id}"):
        return {"message": "post service is not running"}
    
    cache_key = f"post_{post_id}"
    cached_post = get_from_cache(cache_key)
    if cached_post:
        logger.info(f"Post {post_id} found in cache")
        return cached_post

    try:
        response = requests.get(f"{POST_SERVICE_URL}/post/{post_id}")
        post_data = response.json()
        
        set_to_cache(cache_key, post_data)
        logger.info(f"Post {post_id} saved to cache")
        
        return post_data
    except Exception as e:
        logger.error(f"Error getting post {post_id}: {str(e)}")
        return {"error": "Internal server error"}

@app.get("/posts", response_model=list[PostResponse])
async def get_all_posts(skip: int = 0, limit: int = 100, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts"):
        return {"message": "post service is not running"}
    
    try:
        response = requests.get(f"{POST_SERVICE_URL}/posts?skip={skip}&limit={limit}")
        return response.json()
    except Exception as e:
        logger.error(f"Error getting posts: {str(e)}")
        return {"error": "Internal server error"}

@app.put("/post/{post_id}", response_model=PostResponse)
async def update_post(post_id: int, post_data: PostUpdate, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.patch(
            f"{POST_SERVICE_URL}/posts/{post_id}",
            json=post_data.dict(),
            params={"author_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error updating post"))
        return PostResponse(**response.json())
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/post/{post_id}")
async def delete_post(post_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/post/{post_id}"):
        return {"message": "post service is not running"}
    
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/post/{post_id}",
            params={"author_id": user_id}
        )
        if response.status_code == 200:
            # Удаляем пост из кэша при удалении
            cache_key = f"post_{post_id}"
            requests.delete(f"{REDIS_SERVICE_URL}/delete/{cache_key}")
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {str(e)}")
        return {"error": "Internal server error"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
