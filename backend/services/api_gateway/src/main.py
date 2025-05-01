import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import requests
from .config import *
import logging
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel
from typing import List

app = FastAPI(
    title="API Gateway",
    description="API Gateway for microservices",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
FILE_SERVICE_URL = "http://file_service:8005"
NEWS_SERVICE_URL = "http://news_service:8006"

SERVICE_URLS = {
    "auth": AUTH_SERVICE_URL,
    "user": USER_SERVICE_URL,
    "redis": REDIS_SERVICE_URL,
    "post": POST_SERVICE_URL,
    "file": FILE_SERVICE_URL,
    "news": NEWS_SERVICE_URL
}

def get_from_cache(key):
    resp = requests.get(f"{REDIS_SERVICE_URL}/get/{key}")
    if resp.status_code == 200:
        return resp.json()
    return None

def set_to_cache(key, value, expire=300):
    # Если это пост и в нем есть комментарии, устанавливаем меньшее время жизни кеша
    if key.startswith("post_") and value and "comments" in value and value["comments"]:
        expire = 10
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
            
        return credentials.credentials  # Возвращаем сам токен
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def handle_service_response(response, error_prefix: str):
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid token")
    elif response.status_code == 403:
        raise HTTPException(status_code=403, detail=response.json().get("detail", "Access denied"))
    elif response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", f"{error_prefix}"))
    return response.json()

@app.get("/health")
async def root():
    return {"message": "health check"}

@app.post("/auth/register")
async def register(user_data: UserRegister):
    if not check_route_enabled(f"{AUTH_SERVICE_URL}/auth/register"):
        return {"message": "auth service is not running"}
    try:
        logger.info(f"Starting user registration for username: {user_data.username}")
        
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/register",
            json=user_data.dict()
        )
        logger.info(f"Auth service response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Auth service error: {response.json()}")
            return response.json()
            
        user_info = response.json()
        logger.info(f"User created successfully with ID: {user_info.get('id')}")
        
        return user_info
    except ValueError as e:
        logger.error(f"Invalid JSON format: {str(e)}")
        return {
            "error": "Invalid JSON format",
        }
    except Exception as e:
        logger.error(f"Unexpected error in register: {str(e)}")
        return {"error": "Internal server error"}

@app.post("/auth/login")
async def login(user_data: UserLogin):
    if not check_route_enabled(f"{AUTH_SERVICE_URL}/auth/health"):
        return {"message": "auth service is not running"}
    try:     
        response = requests.post(f"{AUTH_SERVICE_URL}/auth/login", json=user_data.dict())
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Login failed"))
        return response.json()
    except ValueError as e:
        return {"error": "Invalid JSON format"}
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

class RefreshToken(BaseModel):
    refresh_token: str

@app.post("/auth/refresh")
async def refresh_token(refresh_data: RefreshToken):
    if not check_route_enabled(f"{AUTH_SERVICE_URL}/auth/refresh"):
        raise HTTPException(status_code=503, detail="Auth service is not running")
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/refresh",
            json=refresh_data.dict()
        )
        return handle_service_response(response, "Failed to refresh token")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

@app.post("/post/create")
async def create_post(
    title: str = Form(...),
    content: str = Form(...),
    images: list[UploadFile] = File(None),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        # Проверяем токен и получаем ID пользователя
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        author_id = user_info["user_id"]
        
        post_data = {
            "title": title,
            "content": content,
            "author_id": author_id,
            "images": []
        }
        
        if images:
            for image in images:
                files = {"file": (image.filename, image.file, image.content_type)}
                upload_response = requests.post(f"{FILE_SERVICE_URL}/upload", files=files)
                if upload_response.status_code != 200:
                    raise HTTPException(status_code=500, detail="Error uploading image")
                
                file_info = upload_response.json()
                post_data["images"].append({"image_url": file_info["url"]})
        
        response = requests.post(
            f"{POST_SERVICE_URL}/posts/",
            json=post_data,
            params={"author_id": author_id}
        )
        return handle_service_response(response, "Error creating post")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/post/{post_id}", response_model=PostResponse)
async def get_post(post_id: int):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.get(f"{POST_SERVICE_URL}/posts/{post_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting post"))
        
        post_data = response.json()
        
        # Добавляем информацию об авторе
        if "author" not in post_data and "author_id" in post_data:
            try:
                author_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{post_data['author_id']}")
                if author_response.status_code == 200:
                    post_data['author'] = author_response.json()
                else:
                    post_data['author'] = {
                        "id": post_data['author_id'],
                        "username": "[Удаленный пользователь]",
                        "full_name": "[Удаленный пользователь]",
                        "about_me": None
                    }
            except Exception as e:
                logger.error(f"Error fetching author for post {post_id}: {str(e)}")
                post_data['author'] = {
                    "id": post_data['author_id'],
                    "username": "[Удаленный пользователь]",
                    "full_name": "[Удаленный пользователь]",
                    "about_me": None
                }
        
        # Добавляем информацию о пользователях для лайков
        if 'likes' in post_data and post_data['likes']:
            for like in post_data['likes']:
                if 'user_id' in like and not 'user' in like:
                    try:
                        user_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{like['user_id']}")
                        if user_response.status_code == 200:
                            like['user'] = user_response.json()
                        else:
                            like['user'] = {
                                "id": like['user_id'],
                                "username": "[Удаленный пользователь]",
                                "full_name": "[Удаленный пользователь]",
                                "about_me": None
                            }
                    except Exception as e:
                        logger.error(f"Error fetching user for like: {str(e)}")
                        like['user'] = {
                            "id": like['user_id'],
                            "username": "[Удаленный пользователь]",
                            "full_name": "[Удаленный пользователь]",
                            "about_me": None
                        }
        
        # Добавляем информацию об авторах для комментариев
        if 'comments' in post_data and post_data['comments']:
            for comment in post_data['comments']:
                if 'author_id' in comment and not 'author' in comment:
                    try:
                        author_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{comment['author_id']}")
                        if author_response.status_code == 200:
                            comment['author'] = author_response.json()
                        else:
                            comment['author'] = {
                                "id": comment['author_id'],
                                "username": "[Удаленный пользователь]",
                                "full_name": "[Удаленный пользователь]",
                                "about_me": None
                            }
                    except Exception as e:
                        logger.error(f"Error fetching author for comment: {str(e)}")
                        comment['author'] = {
                            "id": comment['author_id'],
                            "username": "[Удаленный пользователь]",
                            "full_name": "[Удаленный пользователь]",
                            "about_me": None
                        }
        
        return post_data
    except Exception as e:
        logger.error(f"Error getting post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/posts", response_model=list[PostResponse])
async def get_all_posts(skip: int = 0, limit: int = 100):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.get(f"{POST_SERVICE_URL}/posts?skip={skip}&limit={limit}")
        if response.status_code != 200:
            error_detail = response.json().get("detail", "Error getting posts")
            logger.error(f"Error from post service: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=error_detail)
            
        posts = response.json()
        
        for post in posts:
            # Добавляем информацию об авторе
            if "author" not in post and "author_id" in post:
                try:
                    author_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{post['author_id']}")
                    if author_response.status_code == 200:
                        post['author'] = author_response.json()
                    else:
                        logger.warning(f"Could not get author data for user ID {post['author_id']}")
                        post['author'] = {
                            "id": post['author_id'],
                            "username": "[Удаленный пользователь]",
                            "full_name": "[Удаленный пользователь]",
                            "about_me": None
                        }
                except Exception as e:
                    logger.error(f"Error fetching author for post {post.get('id')}: {str(e)}")
                    post['author'] = {
                        "id": post['author_id'],
                        "username": "[Удаленный пользователь]",
                        "full_name": "[Удаленный пользователь]",
                        "about_me": None
                    }
            
            # Добавляем информацию о пользователях для лайков
            if 'likes' in post and post['likes']:
                for like in post['likes']:
                    if 'user_id' in like and not 'user' in like:
                        try:
                            user_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{like['user_id']}")
                            if user_response.status_code == 200:
                                like['user'] = user_response.json()
                            else:
                                like['user'] = {
                                    "id": like['user_id'],
                                    "username": "[Удаленный пользователь]",
                                    "full_name": "[Удаленный пользователь]",
                                    "about_me": None
                                }
                        except Exception as e:
                            logger.error(f"Error fetching user for like: {str(e)}")
                            like['user'] = {
                                "id": like['user_id'],
                                "username": "[Удаленный пользователь]",
                                "full_name": "[Удаленный пользователь]",
                                "about_me": None
                            }
            
            # Добавляем информацию об авторах для комментариев
            if 'comments' in post and post['comments']:
                for comment in post['comments']:
                    if 'author_id' in comment and not 'author' in comment:
                        try:
                            author_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{comment['author_id']}")
                            if author_response.status_code == 200:
                                comment['author'] = author_response.json()
                            else:
                                comment['author'] = {
                                    "id": comment['author_id'],
                                    "username": "[Удаленный пользователь]",
                                    "full_name": "[Удаленный пользователь]",
                                    "about_me": None
                                }
                        except Exception as e:
                            logger.error(f"Error fetching author for comment: {str(e)}")
                            comment['author'] = {
                                "id": comment['author_id'],
                                "username": "[Удаленный пользователь]",
                                "full_name": "[Удаленный пользователь]",
                                "about_me": None
                            }
                
        return posts
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting posts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/post/{post_id}")
async def update_post(
    post_id: int, 
    post_data: PostUpdate, 
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.patch(
            f"{POST_SERVICE_URL}/posts/{post_id}",
            json=post_data.dict(),
            params={"admin_id": credentials.credentials}
        )
        return handle_service_response(response, "Error updating post")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/post/{post_id}")
async def delete_post(post_id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/posts/{post_id}",
            params={"admin_id": credentials.credentials}
        )
        return handle_service_response(response, "Error deleting post")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/post/{post_id}/comment")
async def create_comment(
    post_id: int, 
    comment_data: CommentCreate, 
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/comments"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        # Проверяем токен и получаем ID пользователя
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        author_id = user_info.get("user_id")
        if not author_id:
            raise HTTPException(status_code=401, detail="Invalid token data")
        
        response = requests.post(
            f"{POST_SERVICE_URL}/posts/{post_id}/comments/",
            json={**comment_data.dict(), "author_id": author_id}
        )
        return handle_service_response(response, "Error creating comment")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating comment for post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/post/{post_id}/comments", response_model=list[CommentResponse])
async def get_post_comments(post_id: int, skip: int = 0, limit: int = 100, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/comments"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.get(
            f"{POST_SERVICE_URL}/posts/{post_id}/comments/",
            params={"skip": skip, "limit": limit}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting comments"))
        
        comments = response.json()
        
        # Добавляем информацию об авторах для комментариев
        for comment in comments:
            if 'author_id' in comment and not 'author' in comment:
                try:
                    author_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{comment['author_id']}")
                    if author_response.status_code == 200:
                        comment['author'] = author_response.json()
                    else:
                        comment['author'] = {
                            "id": comment['author_id'],
                            "username": "[Удаленный пользователь]",
                            "full_name": "[Удаленный пользователь]",
                            "about_me": None
                        }
                except Exception as e:
                    logger.error(f"Error fetching author for comment: {str(e)}")
                    comment['author'] = {
                        "id": comment['author_id'],
                        "username": "[Удаленный пользователь]",
                        "full_name": "[Удаленный пользователь]",
                        "about_me": None
                    }
                    
        return comments
    except Exception as e:
        logger.error(f"Error getting comments for post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/comment/{comment_id}")
async def update_comment(
    comment_id: int, 
    comment_data: CommentUpdate, 
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{POST_SERVICE_URL}/comments/{comment_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.patch(
            f"{POST_SERVICE_URL}/comments/{comment_id}",
            json=comment_data.dict(),
            params={"admin_id": credentials.credentials}
        )
        return handle_service_response(response, "Error updating comment")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating comment {comment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/comment/{comment_id}/admin")
async def admin_delete_comment(comment_id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/comments/health"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        logger.info(f"Admin deleting comment {comment_id}")
        logger.info(f"Credentials: {credentials.credentials}")
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}  
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        admin_id = user_info.get("user_id")
        if not admin_id:
            raise HTTPException(status_code=401, detail="Invalid token data")
            
        # Проверяем права администратора
        if not user_info.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Only administrators can delete comments")
        
        response = requests.delete(
            f"{POST_SERVICE_URL}/comments/{comment_id}",
            params={"admin_id": admin_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting comment"))
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting comment {comment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/post/{post_id}/like")
async def add_like(post_id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/likes"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        # Проверяем токен и получаем ID пользователя
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        user_id = user_info.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token data")
        
        response = requests.post(
            f"{POST_SERVICE_URL}/posts/{post_id}/likes/",
            json={"user_id": user_id}
        )
        return handle_service_response(response, "Error adding like")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error adding like to post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/post/{post_id}/like")
async def remove_like(post_id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/likes"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        # Проверяем токен и получаем ID пользователя
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        user_id = user_info.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token data")
        
        response = requests.delete(
            f"{POST_SERVICE_URL}/posts/{post_id}/likes/{user_id}"
        )
        return handle_service_response(response, "Error removing like")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error removing like from post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/files/{filename}")
async def get_file(filename: str):
    try:
        response = requests.get(f"{FILE_SERVICE_URL}/files/{filename}", stream=True)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="File not found")
        
        return StreamingResponse(
            io.BytesIO(response.content),
            media_type=response.headers.get("content-type", "application/octet-stream")
        )
    except Exception as e:
        logger.error(f"Error getting file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting file")

@app.get("/news/")
async def get_news(skip: int = 0, limit: int = 100, category: str = None):
    if not check_route_enabled(f"{NEWS_SERVICE_URL}/news"):
        raise HTTPException(status_code=503, detail="News service is not running")
    
    try:
        params = {"skip": skip, "limit": limit}
        if category:
            params["category"] = category
            
        response = requests.get(f"{NEWS_SERVICE_URL}/news/", params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting news"))
        return response.json()
    except Exception as e:
        logger.error(f"Error getting news: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/news/{news_id}")
async def get_news_by_id(news_id: int):
    if not check_route_enabled(f"{NEWS_SERVICE_URL}/news/{news_id}"):
        raise HTTPException(status_code=503, detail="News service is not running")
    
    try:
        response = requests.get(f"{NEWS_SERVICE_URL}/news/{news_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting news"))
        return response.json()
    except Exception as e:
        logger.error(f"Error getting news {news_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

class NewsContent(BaseModel):
    type: str
    content: str
    order: int

class NewsCreate(BaseModel):
    title: str
    category: str
    contents: List[NewsContent]

@app.post("/news/")
async def create_news(
    news_data: NewsCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{NEWS_SERVICE_URL}/news"):
        raise HTTPException(status_code=503, detail="News service is not running")
    
    try:
        # Проверяем токен и получаем ID пользователя и права администратора
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Проверяем права администратора
        if not user_info.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Only administrators can create news")
            
        author_id = user_info.get("user_id")
        if not author_id:
            raise HTTPException(status_code=401, detail="Invalid token data")
        
        response = requests.post(
            f"{NEWS_SERVICE_URL}/news/",
            json=news_data.dict(),
            params={"author_id": author_id}
        )
        return handle_service_response(response, "Error creating news")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating news: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/news/{news_id}")
async def update_news(
    news_id: int, 
    news_data: dict, 
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{NEWS_SERVICE_URL}/news/{news_id}"):
        raise HTTPException(status_code=503, detail="News service is not running")
    
    try:
        response = requests.patch(
            f"{NEWS_SERVICE_URL}/news/{news_id}",
            json=news_data,
            params={"admin_id": credentials.credentials}
        )
        return handle_service_response(response, "Error updating news")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating news {news_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/news/{news_id}")
async def delete_news(news_id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not check_route_enabled(f"{NEWS_SERVICE_URL}/news/{news_id}"):
        raise HTTPException(status_code=503, detail="News service is not running")
    
    try:
        response = requests.delete(
            f"{NEWS_SERVICE_URL}/news/{news_id}",
            params={"admin_id": credentials.credentials}
        )
        return handle_service_response(response, "Error deleting news")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting news {news_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/news/stats/categories")
async def get_news_categories_stats():
    if not check_route_enabled(f"{NEWS_SERVICE_URL}/news/stats/categories"):
        raise HTTPException(status_code=503, detail="News service is not running")
    
    try:
        response = requests.get(f"{NEWS_SERVICE_URL}/news/stats/categories")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting news categories stats"))
        return response.json()
    except Exception as e:
        logger.error(f"Error getting news categories stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/post/{post_id}/admin")
async def admin_delete_post(post_id: int, user_id: int = Depends(verify_admin)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/posts/{post_id}/admin",
            params={"admin_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting post"))
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not check_route_enabled(f"{FILE_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="File service is not running")
    
    try:
        # Проверяем токен
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        user_info = user_response.json()
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Проверяем тип файла
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
            
        # Отправляем файл в file_service
        files = {"file": (file.filename, file.file, file.content_type)}
        response = requests.post(f"{FILE_SERVICE_URL}/upload", files=files)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Error uploading file")
            
        file_info = response.json()
        return {
            "url": f"/files/{file_info['filename']}",
            "filename": file_info['filename'],
            "size": file_info['size'],
            "content_type": file_info['content_type']
        }
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
