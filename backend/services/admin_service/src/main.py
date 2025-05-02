from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
import logging
from typing import List, Dict

app = FastAPI(
    title="Admin Service",
    description="Service for administrative operations",
    version="1.0.0"
)

security = HTTPBearer()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = "http://auth_service:8001"
USER_SERVICE_URL = "http://user_service:8002"
POST_SERVICE_URL = "http://post_service:8004"
NEWS_SERVICE_URL = "http://news_service:8006"

async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if not response.json():
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_data = response.json()
        if not user_data.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Not authorized as admin")
            
        return user_data["user_id"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.delete("/posts/{post_id}")
async def delete_post(post_id: int, admin_id: int = Depends(verify_admin)):
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/posts/{post_id}/admin",
            params={"admin_id": admin_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting post"))
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int, admin_id: int = Depends(verify_admin)):
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/comments/{comment_id}/admin",
            params={"admin_id": admin_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting comment"))
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting comment {comment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/news")
async def create_news(news_data: dict, admin_id: int = Depends(verify_admin)):
    try:
        response = requests.post(
            f"{NEWS_SERVICE_URL}/news/",
            json=news_data,
            params={"author_id": admin_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error creating news"))
        return response.json()
    except Exception as e:
        logger.error(f"Error creating news: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/news/{news_id}")
async def update_news(news_id: int, news_data: dict, admin_id: int = Depends(verify_admin)):
    try:
        response = requests.patch(
            f"{NEWS_SERVICE_URL}/news/{news_id}",
            json=news_data,
            params={"author_id": admin_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error updating news"))
        return response.json()
    except Exception as e:
        logger.error(f"Error updating news {news_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/news/{news_id}")
async def delete_news(news_id: int, admin_id: int = Depends(verify_admin)):
    try:
        response = requests.delete(
            f"{NEWS_SERVICE_URL}/news/{news_id}",
            params={"author_id": admin_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting news"))
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting news {news_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats/posts")
async def get_posts_stats(admin_id: int = Depends(verify_admin)):
    try:
        response = requests.get(f"{POST_SERVICE_URL}/posts/stats")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting posts stats"))
        return response.json()
    except Exception as e:
        logger.error(f"Error getting posts stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/stats/news")
async def get_news_stats(admin_id: int = Depends(verify_admin)):
    try:
        response = requests.get(f"{NEWS_SERVICE_URL}/news/stats/categories")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting news stats"))
        return response.json()
    except Exception as e:
        logger.error(f"Error getting news stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 