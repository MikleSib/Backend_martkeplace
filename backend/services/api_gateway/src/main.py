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
from pydantic import EmailStr
import random
import aiohttp
from requests_toolbelt.multipart.encoder import MultipartEncoder

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
MAIL_SERVICE_URL = "http://mail_service:8008"
FORUM_SERVICE_URL = "http://forum_service:8009"

SERVICE_URLS = {
    "auth": AUTH_SERVICE_URL,
    "user": USER_SERVICE_URL,
    "redis": REDIS_SERVICE_URL,
    "post": POST_SERVICE_URL,
    "file": FILE_SERVICE_URL,
    "news": NEWS_SERVICE_URL,
    "mail": MAIL_SERVICE_URL,
    "forum": FORUM_SERVICE_URL
}

def get_from_cache(key):
    resp = requests.get(f"{REDIS_SERVICE_URL}/get/{key}")
    if resp.status_code == 200:
        return resp.json()
    return None

def set_to_cache(key, value, expire=300):
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
            
        return credentials.credentials  
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
        
        # Регистрируем пользователя с неподтвержденным email
        user_data.is_email_verified = False
        
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
        
        # Отправляем код подтверждения на email
        verification_result = await send_verification_code(user_data.email)
        
        # Возвращаем информацию о созданном пользователе и о необходимости подтверждения email
        return {
            **user_info,
            "email_verification": {
                "required": True,
                "email": user_data.email,
                "expires_in": verification_result.get("expires_in", 900)
            }
        }
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
        
        user_info = response.json()
        
        # Проверяем, подтвержден ли email
        is_verified = user_info.get("is_email_verified", False)
        
        user_email = user_info.get("email")
        if not user_email and "user" in user_info and user_info["user"].get("email"):
            user_email = user_info["user"].get("email")
        
        if not user_email:
            # Получаем email пользователя из базы данных, если его нет в ответе
            logger.info(f"Получение email для пользователя {user_info.get('username')}")
            user_id = user_info.get("id")
            if "user" in user_info and user_info["user"].get("id"):
                user_id = user_info["user"].get("id")
                
            if user_id:
                email_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
                
                if email_response.status_code == 200:
                    user_email = email_response.json().get("email")
                
        if user_email:
            # Проверяем верификацию в Redis (временное решение)
            verified_key = f"email_verified_{user_email}"
            verification_response = requests.get(f"{REDIS_SERVICE_URL}/get/{verified_key}")
            logger.info(f"Проверка верификации в Redis: {verified_key}, ответ: {verification_response.status_code}, значение: {verification_response.text}")
            
            if verification_response.status_code == 200:
                try:
                    redis_value = verification_response.json()
                    if redis_value == "true" or redis_value == True:
                        # Если в Redis отмечено, что email верифицирован
                        is_verified = True
                        # Обновим is_email_verified в user_info
                        if "user" in user_info:
                            user_info["user"]["is_email_verified"] = True
                        else:
                            user_info["is_email_verified"] = True
                        logger.info(f"Email {user_email} подтвержден (из Redis)")
                except Exception as e:
                    logger.error(f"Ошибка при проверке ключа в Redis: {str(e)}")
        
        if not is_verified and user_email:
            # Если email не подтвержден, отправляем новый код 
            logger.info(f"Login attempt for user with unverified email: {user_email}")
            
            # Отправляем новый код подтверждения
            verification_result = await send_verification_code(user_email)
            
            return {
                **user_info,
                "email_verification": {
                    "required": True,
                    "message": "Email не подтвержден. Новый код был отправлен на вашу почту.",
                    "email": user_email,
                    "expires_in": verification_result.get("expires_in", 900)
                }
            }
        elif not user_email:
            # Если email всё ещё не найден, вернём ошибку
            logger.error("Не удалось получить email пользователя")
            return {
                **user_info,
                "email_verification": {
                    "required": True,
                    "message": "Email не подтвержден, но не удалось отправить код.",
                    "error": "Не найден email пользователя"
                }
            }
        
        return user_info
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
        
        user_response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid token")
        elif user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to verify token")
            
        logger.info(f"Auth service response status: {user_response.status_code}")
        logger.info(f"Auth service response content: {user_response.content}")
        
        try:
            user_info = user_response.json()
            logger.info(f"User info from auth service: {user_info}")
        except Exception as e:
            logger.error(f"Error parsing auth response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error parsing auth response: {str(e)}")
            
        # Проверяем, что токен валидный
        if not user_info.get("valid", False):
            error_message = user_info.get("message", "Invalid token")
            raise HTTPException(status_code=401, detail=error_message)
            
        logger.info(f"Type of user_info: {type(user_info)}")
        
        # Получаем ID пользователя из ответа auth_service
        author_id = user_info.get("user_id")
        logger.info(f"Author ID from user_info: {author_id}")
        
        if not author_id:
            raise HTTPException(status_code=401, detail="Could not determine user ID")
        
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
            json=post_data
        )
        
        logger.info(f"Response status from post service: {response.status_code}")
        logger.info(f"Response content: {response.content}")
        
        try:
            response_data = response.json()
            logger.info(f"Response JSON: {response_data}")
            return response_data
        except Exception as e:
            logger.error(f"Error parsing response JSON: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating post: {str(e)}")
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
        
        # Корректная передача бинарных данных как поток
        return StreamingResponse(
            io.BytesIO(response.content),
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error getting file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting file: {str(e)}")

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
            
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # Проверка размера файла
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File size exceeds the limit of {MAX_FILE_SIZE/1024/1024}MB"
            )
        
        # Перематываем файл обратно на начало
        await file.seek(0)
        
        # Передаем файл напрямую
        files = {"file": (file.filename, file.file, file.content_type)}
        response = requests.post(f"{FILE_SERVICE_URL}/upload", files=files)
        
        if response.status_code != 200 and response.status_code != 201:
            error_message = "Error uploading file"
            try:
                error_data = response.json()
                if "detail" in error_data:
                    error_message = error_data["detail"]
            except:
                pass
            raise HTTPException(status_code=response.status_code, detail=error_message)
            
        return response.json()
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@app.post("/test")
async def test(to_email: EmailStr):
    """
    Простой тестовый эндпоинт для отправки письма
    """
    try:
        logger.info(f"Отправка тестового письма на {to_email}")
        
        # Отправляем запрос к mail_service
        response = requests.post(
            f"{MAIL_SERVICE_URL}/test",
            json={"to_email": to_email}
        )
        
        if response.status_code != 200:
            logger.error(f"Ошибка отправки тестового письма: {response.text}")
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"Ошибка отправки письма: {response.json().get('detail', 'Unknown error')}"
            )
        
        return {
            "status": "success",
            "message": "Тестовое письмо успешно отправлено"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при тестировании почтового сервиса: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при тестировании почтового сервиса: {str(e)}")

@app.post("/auth/send-verification")
async def send_verification_code(to_email: EmailStr):
    """
    Отправляет код подтверждения на указанную почту
    """
    try:
        # Генерируем 6-значный код
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        logger.info(f"Отправка кода подтверждения на {to_email}, код: {verification_code}")
        
        # Отправляем запрос к mail_service
        response = requests.post(
            f"{MAIL_SERVICE_URL}/send-verification",
            json={"to_email": to_email, "code": verification_code}
        )
        
        if response.status_code != 200:
            logger.error(f"Ошибка отправки кода подтверждения: {response.text}")
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"Ошибка отправки кода: {response.json().get('detail', 'Unknown error')}"
            )
        
        # Сохраняем код в кэш с временем жизни 15 минут
        verification_key = f"verification_code_{to_email}"
        requests.post(
            f"{REDIS_SERVICE_URL}/set",
            json={"key": verification_key, "value": verification_code, "expire": 900}  # 15 минут = 900 секунд
        )
        
        return {
            "status": "success",
            "message": "Код подтверждения отправлен",
            "expires_in": 900  # 15 минут в секундах
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при отправке кода подтверждения: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке кода подтверждения: {str(e)}")

@app.post("/auth/verify-email")
async def verify_email(to_email: EmailStr, code: str):
    """
    Проверяет код подтверждения email и обновляет статус верификации пользователя
    """
    try:
        # Получаем код из кэша
        verification_key = f"verification_code_{to_email}"
        response = requests.get(f"{REDIS_SERVICE_URL}/get/{verification_key}")
        
        if response.status_code != 200 or not response.json():
            logger.warning(f"Код для {to_email} не найден или истек срок его действия")
            
            # Генерируем новый код и отправляем его
            verification_result = await send_verification_code(to_email)
            return {
                "status": "error",
                "verified": False,
                "message": "Срок действия кода истек. Отправлен новый код.",
                "expires_in": verification_result.get("expires_in", 900)
            }
            
        saved_code = response.json()
        
        if saved_code != code:
            logger.warning(f"Неверный код для {to_email}: ожидался {saved_code}, получен {code}")
            return {
                "status": "error",
                "verified": False,
                "message": "Неверный код подтверждения"
            }
        
        # Код верный, отмечаем email как подтвержденный
        # Удаляем код из кэша, так как он больше не нужен
        delete_response = requests.delete(f"{REDIS_SERVICE_URL}/delete/{verification_key}")
        logger.info(f"Удаление ключа верификации: {verification_key}, статус: {delete_response.status_code}")
        
        # ВРЕМЕННОЕ РЕШЕНИЕ: Поскольку эндпоинт /auth/verify-email еще не реализован,
        # мы просто отмечаем в Redis, что email подтвержден
        verified_key = f"email_verified_{to_email}"
        set_response = requests.post(
            f"{REDIS_SERVICE_URL}/set",
            json={"key": verified_key, "value": "true", "expire": 31536000}  # 1 год
        )
        logger.info(f"Установка ключа верификации: {verified_key}, статус: {set_response.status_code}")
        
        # Находим пользователя по email, чтобы вернуть его данные
        # В будущем заменить на вызов auth_service, когда эндпоинт будет готов
        try:
            # Поиск пользователя по email
            user_info = {"email": to_email, "is_email_verified": True}
            
            return {
                "status": "success",
                "verified": True,
                "message": "Email успешно подтвержден",
                "user": user_info
            }
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя: {str(e)}")
            return {
                "status": "success",
                "verified": True,
                "message": "Email успешно подтвержден, но информация о пользователе недоступна",
            }
            
    except Exception as e:
        logger.error(f"Ошибка при проверке кода подтверждения: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при проверке кода подтверждения: {str(e)}")

# ФОРУМ ЭНДПОИНТЫ
# Категории форума
@app.get("/forum/categories")
async def get_forum_categories():
    """Получение списка всех корневых категорий форума"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.get(f"{FORUM_SERVICE_URL}/api/v1/categories")
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении категорий форума")
        )
    
    return response.json()

@app.get("/forum/categories/{category_id}")
async def get_forum_category(category_id: int):
    """Получение данных категории с подкатегориями"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.get(f"{FORUM_SERVICE_URL}/api/v1/categories/{category_id}")
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении категории форума")
        )
    
    return response.json()

@app.post("/forum/categories")
async def create_forum_category(category_data: dict, token: str = Depends(verify_admin)):
    """Создание новой категории форума (только для администраторов)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.post(
        f"{FORUM_SERVICE_URL}/api/v1/categories",
        headers={"Authorization": f"Bearer {token}"},
        json=category_data
    )
    
    if response.status_code != 201:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при создании категории форума")
        )
    
    return response.json()

@app.put("/forum/categories/{category_id}")
async def update_forum_category(category_id: int, category_data: dict, token: str = Depends(verify_admin)):
    """Обновление категории форума (только для администраторов)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.put(
        f"{FORUM_SERVICE_URL}/api/v1/categories/{category_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=category_data
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при обновлении категории форума")
        )
    
    return response.json()

@app.delete("/forum/categories/{category_id}")
async def delete_forum_category(category_id: int, token: str = Depends(verify_admin)):
    """Удаление категории форума (только для администраторов)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.delete(
        f"{FORUM_SERVICE_URL}/api/v1/categories/{category_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 204:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при удалении категории форума")
        )
    
    return {"message": "Категория успешно удалена"}

# Темы форума
@app.get("/forum/topics")
async def get_forum_topics(
    category_id: int = None, 
    author_id: int = None, 
    pinned: bool = None,
    page: int = 1,
    page_size: int = 20
):
    """Получение списка тем с пагинацией и фильтрацией"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    params = {
        "page": page,
        "page_size": page_size
    }
    
    if category_id is not None:
        params["category_id"] = category_id
    if author_id is not None:
        params["author_id"] = author_id
    if pinned is not None:
        params["pinned"] = pinned
    
    response = requests.get(
        f"{FORUM_SERVICE_URL}/api/v1/topics",
        params=params
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении списка тем форума")
        )
    
    return response.json()

@app.get("/forum/topics/{topic_id}")
async def get_forum_topic(topic_id: int):
    """Получение детальной информации о теме"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.get(f"{FORUM_SERVICE_URL}/api/v1/topics/{topic_id}")
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении темы форума")
        )
    
    return response.json()

@app.post("/forum/topics")
async def create_forum_topic(topic_data: dict, user_id: int = Depends(verify_token)):
    """Создание новой темы с первым сообщением"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.post(
        f"{FORUM_SERVICE_URL}/api/v1/topics",
        headers={"Authorization": f"Bearer {user_id}"},
        json=topic_data
    )
    
    if response.status_code != 201:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при создании темы форума")
        )
    
    return response.json()

@app.put("/forum/topics/{topic_id}")
async def update_forum_topic(topic_id: int, topic_data: dict, user_id: int = Depends(verify_token)):
    """Обновление темы (владельцем или модератором)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.put(
        f"{FORUM_SERVICE_URL}/api/v1/topics/{topic_id}",
        headers={"Authorization": f"Bearer {user_id}"},
        json=topic_data
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при обновлении темы форума")
        )
    
    return response.json()

@app.delete("/forum/topics/{topic_id}")
async def delete_forum_topic(topic_id: int, user_id: int = Depends(verify_token)):
    """Удаление темы (владельцем или модератором)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.delete(
        f"{FORUM_SERVICE_URL}/api/v1/topics/{topic_id}",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 204:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при удалении темы форума")
        )
    
    return {"message": "Тема успешно удалена"}

@app.put("/forum/topics/{topic_id}/pin")
async def pin_forum_topic(topic_id: int, user_id: int = Depends(verify_token)):
    """Закрепление/открепление темы (только для модераторов)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.put(
        f"{FORUM_SERVICE_URL}/api/v1/topics/{topic_id}/pin",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при закреплении/откреплении темы форума")
        )
    
    return response.json()

@app.put("/forum/topics/{topic_id}/close")
async def close_forum_topic(topic_id: int, user_id: int = Depends(verify_token)):
    """Закрытие/открытие темы (только для модераторов)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.put(
        f"{FORUM_SERVICE_URL}/api/v1/topics/{topic_id}/close",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при закрытии/открытии темы форума")
        )
    
    return response.json()

# Сообщения форума
@app.get("/forum/posts")
async def get_forum_posts(
    topic_id: int,
    page: int = 1, 
    page_size: int = 20
):
    """Получение списка сообщений в теме с пагинацией"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    params = {
        "topic_id": topic_id,
        "page": page,
        "page_size": page_size
    }
    
    response = requests.get(
        f"{FORUM_SERVICE_URL}/api/v1/posts",
        params=params
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении списка сообщений форума")
        )
    
    return response.json()

@app.get("/forum/posts/{post_id}")
async def get_forum_post(post_id: int):
    """Получение подробной информации о сообщении"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.get(f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}")
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении сообщения форума")
        )
    
    return response.json()

@app.post("/forum/posts")
async def create_forum_post(post_data: dict, user_id: int = Depends(verify_token)):
    """Создание нового сообщения в теме"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.post(
        f"{FORUM_SERVICE_URL}/api/v1/posts",
        headers={"Authorization": f"Bearer {user_id}"},
        json=post_data
    )
    
    if response.status_code != 201:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при создании сообщения форума")
        )
    
    return response.json()

@app.put("/forum/posts/{post_id}")
async def update_forum_post(post_id: int, post_data: dict, user_id: int = Depends(verify_token)):
    """Обновление сообщения (владельцем или модератором)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.put(
        f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}",
        headers={"Authorization": f"Bearer {user_id}"},
        json=post_data
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при обновлении сообщения форума")
        )
    
    return response.json()

@app.delete("/forum/posts/{post_id}")
async def delete_forum_post(post_id: int, user_id: int = Depends(verify_token)):
    """Удаление сообщения (владельцем или модератором)"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.delete(
        f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 204:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при удалении сообщения форума")
        )
    
    return {"message": "Сообщение успешно удалено"}

@app.post("/forum/posts/{post_id}/like")
async def like_forum_post(post_id: int, user_id: int = Depends(verify_token)):
    """Лайк сообщения"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.post(
        f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при добавлении лайка")
        )
    
    return response.json()

@app.post("/forum/posts/{post_id}/dislike")
async def dislike_forum_post(post_id: int, user_id: int = Depends(verify_token)):
    """Дизлайк сообщения"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.post(
        f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}/dislike",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при добавлении дизлайка")
        )
    
    return response.json()

@app.delete("/forum/posts/{post_id}/reactions")
async def remove_forum_post_reaction(post_id: int, user_id: int = Depends(verify_token)):
    """Удаление реакции пользователя на сообщение"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.delete(
        f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}/reactions",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при удалении реакции")
        )
    
    return response.json()

@app.get("/forum/active-topics")
async def get_top_active_forum_topics(limit: int = 5):
    """Получение тем с наибольшим количеством сообщений из любых категорий"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    response = requests.get(
        f"{FORUM_SERVICE_URL}/api/v1/active-topics",
        params={"limit": limit}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, 
            detail=response.json().get("detail", "Ошибка при получении активных тем форума")
        )
    
    return response.json()

@app.post("/forum/posts/upload_image")
async def upload_forum_image(
    file: UploadFile = File(...),
    user_id: int = Depends(verify_token)
):
    """Загрузка изображения для сообщения форума"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/health"):
        raise HTTPException(status_code=503, detail="Сервис форума недоступен")
    
    # Проверяем MIME тип файла
    content_type = file.content_type.lower()
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Загружаемый файл должен быть изображением"
        )
    
    try:
        # Копируем содержимое файла во временный буфер для безопасной передачи
        file_content = await file.read()
        
        # Используем requests-toolbelt для корректной отправки файлов
        import io
        
        form_data = MultipartEncoder(
            fields={
                'file': (file.filename, io.BytesIO(file_content), file.content_type)
            }
        )
        
        response = requests.post(
            f"{FORUM_SERVICE_URL}/api/v1/posts/upload_image",
            headers={
                "Authorization": f"Bearer {user_id}",
                "Content-Type": form_data.content_type
            },
            data=form_data
        )
        
        if response.status_code != 201:
            error_message = "Ошибка при загрузке изображения"
            try:
                error_data = response.json()
                if "detail" in error_data:
                    error_message = error_data["detail"]
            except Exception:
                pass
            
            raise HTTPException(
                status_code=response.status_code,
                detail=error_message
            )
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка при загрузке изображения: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при загрузке изображения: {str(e)}"
        )

# Для запуска сервиса напрямую через Python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
