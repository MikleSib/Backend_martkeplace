import uvicorn
from fastapi import FastAPI , Request
import requests
from .config import UserRegister, UserLogin

app = FastAPI()
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = "http://auth_service:8001"
USER_SERVICE_URL = "http://user_service:8002"
REDIS_SERVICE_URL = "http://redis_service:8003"

SERVICE_URLS = {
    "auth": AUTH_SERVICE_URL,
    "user": USER_SERVICE_URL,
    "redis": REDIS_SERVICE_URL
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
        service_name = next((name for name in SERVICE_URLS.keys() if f"/{name}/" in route), None)
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
