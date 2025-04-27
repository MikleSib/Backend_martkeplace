import uvicorn
from fastapi import FastAPI , Request
import requests
from .config import UserRegister, UserLogin

app = FastAPI()

AUTH_SERVICE_URL = "http://auth_service:8001"
USER_SERVICE_URL = "http://user_service:8002"


def check_route_enabled(route: str) -> bool:
    try:
        service_base_url = route.split('/auth/')[0]  
        response = requests.get(f"{service_base_url}/health")
        if response.status_code == 200:
            return True
        return False
    except requests.RequestException as e:
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
