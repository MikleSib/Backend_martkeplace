import uvicorn
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import requests
from .config import *
import logging
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Optional
from pydantic import EmailStr
import random
import aiohttp
from requests_toolbelt.multipart.encoder import MultipartEncoder
import httpx
from fastapi.responses import JSONResponse
from starlette.responses import Response, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
MARKETPLACE_SERVICE_URL = "http://marketplace_service:8010"

SERVICE_URLS = {
    "auth": AUTH_SERVICE_URL,
    "user": USER_SERVICE_URL,
    "redis": REDIS_SERVICE_URL,
    "post": POST_SERVICE_URL,
    "file": FILE_SERVICE_URL,
    "news": NEWS_SERVICE_URL,
    "mail": MAIL_SERVICE_URL,
    "forum": FORUM_SERVICE_URL,
    "marketplace": MARKETPLACE_SERVICE_URL
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
async def register(request: Request):
    """
    Регистрация нового пользователя
    
    Тело запроса (JSON):
    - **username**: Имя пользователя
    - **email**: Электронная почта пользователя
    - **password**: Пароль пользователя
    - **full_name**: Полное имя (опционально)
    - **about_me**: О себе (опционально)
    """
    try:
        body = await request.json()
        
        # Приводим email к нижнему регистру
        if "email" in body:
            body["email"] = body["email"].lower()
        
        async with httpx.AsyncClient() as client:
            # Делаем запрос к auth_service
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/register",
                json=body
            )
            
            # Получаем содержимое ответа
            try:
                response_json = response.json()
            except:
                response_json = {"detail": response.text or "Ошибка сервера"}
            
            # Если статус не 200, возвращаем ошибку с тем же статус-кодом
            if response.status_code != 200:
                return JSONResponse(
                    content=response_json,
                    status_code=response.status_code
                )
            
            # Если регистрация успешна, отправляем код подтверждения на почту
            if "email" in response_json:
                try:
                    # Генерируем 6-значный код подтверждения
                    verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    
                    # Сохраняем код в Redis для последующей проверки
                    verification_key = f"verification_code_{response_json['email']}"
                    redis_response = await client.post(
                        f"{REDIS_SERVICE_URL}/set",
                        json={"key": verification_key, "value": verification_code, "expire": 900}  # 15 минут
                    )
                    logger.info(f"Verification code saved to Redis: {redis_response.status_code}")
                    
                    # Отправляем код на почту пользователя
                    mail_response = await client.post(
                        f"{MAIL_SERVICE_URL}/send-verification",
                        json={
                            "to_email": response_json["email"],
                            "code": verification_code
                        }
                    )
                    logger.info(f"Mail service response: {mail_response.status_code}, {mail_response.text}")
                except Exception as mail_err:
                    logger.error(f"Error sending verification email: {str(mail_err)}")
                    # Не прерываем регистрацию, если отправка письма не удалась
            
            # Возвращаем ответ с тем же статус-кодом
            return JSONResponse(
                content=response_json,
                status_code=response.status_code
            )
            
    except Exception as e:
        logger.exception(f"Registration error: {str(e)}")
        return JSONResponse(
            content={"detail": f"Ошибка сервера: {str(e)}"},
            status_code=500
        )

# Для /api/auth/register можно сделать переадресацию
@app.post("/api/auth/register")
async def api_register(request: Request):
    """API версия эндпоинта регистрации"""
    return await register(request)

@app.post("/api/auth/login")
async def login(request: Request):
    """
    Вход в систему по email и паролю
    
    Тело запроса (JSON):
    - **email**: Электронная почта пользователя
    - **password**: Пароль пользователя
    """
    try:
        body = await request.json()
        email = body.get("email", "").lower()  # Приводим email к нижнему регистру
        password = body.get("password")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Требуются оба поля: email и password")
        
        # Исправляем структуру try-except с async with
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{AUTH_SERVICE_URL}/auth/login",
                    json={"email": email, "password": password}
                )
                
                if response.status_code != 200:
                    if response.status_code == 400:
                        raise HTTPException(status_code=400, detail="Неверный email или пароль")
                    elif response.status_code == 403 and "подтвердить email" in response.text:
                        raise HTTPException(status_code=403, detail="Необходимо подтвердить email перед входом в систему")
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"Ошибка авторизации: {response.text}"
                    )
                
                return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка HTTP: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@app.post("/auth/login")
async def legacy_login(request: Request):
    """
    Вход в систему по email и паролю
    
    Тело запроса (JSON):
    - **email**: Электронная почта пользователя
    - **password**: Пароль пользователя
    """
    try:
        body = await request.json()
        email = body.get("email", "").lower()  # Приводим email к нижнему регистру
        password = body.get("password")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Требуются оба поля: email и password")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{AUTH_SERVICE_URL}/auth/login",
                    json={"email": email, "password": password}
                )
                
                if response.status_code != 200:
                    if response.status_code == 400:
                        raise HTTPException(status_code=400, detail="Неверный email или пароль")
                    elif response.status_code == 403 and "подтвердить email" in response.text:
                        raise HTTPException(status_code=403, detail="Необходимо подтвердить email перед входом в систему")
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"Ошибка авторизации: {response.text}"
                    )
                
                return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка HTTP: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

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
                logger.info(f"Author response: {author_response.json()}")
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
async def verify_email(to_email: str, code: str):
    """
    Проверяет код подтверждения email и обновляет статус верификации пользователя
    
    Параметры запроса:
    - **to_email**: Email пользователя
    - **code**: Код подтверждения из письма
    """
    try:
        email = to_email.lower()
        
        if not email or not code:
            return JSONResponse(
                content={"detail": "Email и код подтверждения обязательны"},
                status_code=400
            )
        
        async with httpx.AsyncClient() as client:
            # Получаем код из Redis
            verification_key = f"verification_code_{email}"
            redis_response = await client.get(f"{REDIS_SERVICE_URL}/get/{verification_key}")
            
            if redis_response.status_code != 200 or not redis_response.json():
                return JSONResponse(
                    content={
                        "status": "error",
                        "verified": False,
                        "message": "Срок действия кода истек. Запросите новый код."
                    },
                    status_code=400
                )
                
            saved_code = redis_response.json()
            
            if saved_code != code:
                return JSONResponse(
                    content={
                        "status": "error",
                        "verified": False,
                        "message": "Неверный код подтверждения"
                    },
                    status_code=400
                )
            
            # Код верный, обновляем статус верификации в auth_service
            auth_response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/verify-email",
                params={"email": email, "code": code}
            )
            
            if auth_response.status_code != 200:
                return JSONResponse(
                    content={
                        "status": "error",
                        "verified": False,
                        "message": f"Ошибка верификации: {auth_response.text}"
                    },
                    status_code=auth_response.status_code
                )
            
            # Удаляем код из Redis, так как он использован
            await client.delete(f"{REDIS_SERVICE_URL}/delete/{verification_key}")
            
            return JSONResponse(
                content={
                    "status": "success",
                    "verified": True,
                    "message": "Email успешно подтвержден",
                    "user": auth_response.json()
                },
                status_code=200
            )
            
    except Exception as e:
        logger.exception(f"Email verification error: {str(e)}")
        return JSONResponse(
            content={"detail": f"Ошибка сервера: {str(e)}"},
            status_code=500
        )

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

@app.post("/forum/posts/{post_id}/report")
async def report_forum_post(post_id: int, report_data: dict, user_id: int = Depends(verify_token)):
    """Отправка жалобы на сообщение форума"""
    if not check_route_enabled(f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}/report"):
        return {"message": "forum service is not running"}
    response = requests.post(
        f"{FORUM_SERVICE_URL}/api/v1/posts/{post_id}/report",
        json=report_data,
        headers={"Authorization": f"Bearer {user_id}"}
    )
    return handle_service_response(response, "Failed to send report for forum post")

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

# Эндпоинт для загрузки и обновления аватара пользователя
@app.post("/api/user/avatar", tags=["Пользователи"])
async def upload_and_update_avatar(
    file: UploadFile = File(...),
    user_id: int = Depends(verify_token),
    token: str = Depends(verify_token)
):
    """
    Загружает новую аватарку пользователя и обновляет его профиль
    
    - **file**: Файл изображения аватара
    - Авторизация: Требуется Bearer токен
    """
    # Загрузка файла
    file_service_url = f"{FILE_SERVICE_URL}/upload"
    files = {"file": (file.filename, await file.read(), file.content_type)}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(file_service_url, files=files)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ошибка загрузки файла: {response.text}"
            )
    
    file_data = response.json()
    file_url = file_data["url"]
    
    # Обновление аватара в профиле пользователя
    user_service_url = f"{USER_SERVICE_URL}/user/avatar"
    params = {"user_id": user_id, "file_url": file_url}
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(user_service_url, params=params, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ошибка обновления аватара: {response.text}"
            )
    
    return response.json()

# Модель для данных профиля
class UserProfileUpdate(BaseModel):
    username: str
    about_me: str = None

# Исправленный эндпоинт для обновления профиля
@app.put("/api/user/profile", tags=["Пользователи"])
async def update_user_profile(
    user_data: UserProfileUpdate,  # Явно указываем, что данные из тела запроса
    user_id: int = Depends(verify_token),
    token: str = Depends(verify_token)
):
    """
    Обновляет данные профиля пользователя
    
    - **username**: Новое имя пользователя (должно быть уникальным)
    - **about_me**: Информация о пользователе
    - Авторизация: Требуется Bearer токен
    """
    user_service_url = f"{USER_SERVICE_URL}/user/profile/update"
    params = {
        "user_id": user_id,
        "username": user_data.username
    }
    
    if user_data.about_me is not None:
        params["about_me"] = user_data.about_me
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put(user_service_url, params=params, headers=headers)
        
        if response.status_code != 200:
            if response.status_code == 400 and "уже существует" in response.text:
                raise HTTPException(
                    status_code=400,
                    detail="Пользователь с таким именем уже существует"
                )
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ошибка обновления профиля: {response.text}"
            )
    
    return response.json()

# Изменено с DELETE на POST
@app.post("/api/user/avatar/delete", tags=["Пользователи"])
async def delete_user_avatar(
    user_id: int = Depends(verify_token),
    token: str = Depends(verify_token)
):
    """
    Удаляет аватар пользователя
    
    - Авторизация: Требуется Bearer токен
    """
    user_service_url = f"{USER_SERVICE_URL}/user/avatar/delete"
    params = {"user_id": user_id}
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(user_service_url, params=params, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ошибка удаления аватара: {response.text}"
            )
    
    return response.json()

# Минимальная версия эндпоинта получения профиля
@app.get("/api/user/profile/me")
async def get_current_user_profile(request: Request):
    """Получает данные профиля текущего пользователя и email из JWT токена"""
    # Извлекаем токен из заголовка
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует токен авторизации")
    
    token = auth_header.replace("Bearer ", "")
    
    # Проверяем токен в auth_service
    async with httpx.AsyncClient() as client:
        auth_response = await client.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": token}
        )
        
        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_data = auth_response.json()
        logger.info(f"User data: {user_data}")
        user_id = user_data.get("user_id")
        user_email = user_data.get("email") 

        if not user_id:
            raise HTTPException(status_code=401, detail="Токен не содержит ID пользователя")
        
        # Получаем профиль из user_service
        user_response = await client.get(
            f"{USER_SERVICE_URL}/user/profile/{user_id}"  # используем существующий endpoint
        )
        
        if user_response.status_code != 200:
            if user_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Профиль не найден")
            raise HTTPException(
                status_code=user_response.status_code,
                detail=f"Ошибка получения профиля: {user_response.text}"
            )
        profile_data = user_response.json()
        profile_data["email"] = user_email 
        return profile_data
    

# Минимальная версия эндпоинта обновления профиля
@app.put("/api/user/profile")
async def update_user_profile(request: Request):
    """Обновляет данные профиля пользователя"""
    # Извлекаем токен из заголовка
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует токен авторизации")
    
    token = auth_header.replace("Bearer ", "")
    
    # Получаем тело запроса
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Неверный формат JSON")
    
    # Проверяем токен в auth_service
    async with httpx.AsyncClient() as client:
        auth_response = await client.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": token}
        )
        
        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_data = auth_response.json()
        user_id = user_data.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Токен не содержит ID пользователя")
        
        # Обновляем профиль через существующий endpoint
        profile_data = body.copy()
        profile_data["user_id"] = user_id
        
        user_response = await client.patch(
            f"{USER_SERVICE_URL}/user/profile/{user_id}",
            json=profile_data
        )
        
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=user_response.status_code,
                detail=f"Ошибка обновления профиля: {user_response.text}"
            )
        
        return user_response.json()

# Минимальная версия эндпоинта удаления аватара
@app.post("/api/user/avatar/delete")
async def delete_user_avatar(request: Request):
    """Удаляет аватар пользователя"""
    # Извлекаем токен из заголовка
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует токен авторизации")
    
    token = auth_header.replace("Bearer ", "")
    
    # Проверяем токен в auth_service
    async with httpx.AsyncClient() as client:
        auth_response = await client.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": token}
        )
        
        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_data = auth_response.json()
        user_id = user_data.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Токен не содержит ID пользователя")
        
        # Обновляем профиль, устанавливая аватар в NULL
        profile_update = {"avatar": None}
        user_response = await client.patch(
            f"{USER_SERVICE_URL}/user/profile/{user_id}",
            json=profile_update
        )
        
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=user_response.status_code,
                detail=f"Ошибка удаления аватара: {user_response.text}"
            )
        
        return user_response.json()

@app.post("/api/user/change-password", tags=["Пользователи"])
async def change_password(request: Request):
    """
    Изменяет пароль пользователя
    
    Тело запроса (JSON):
    - **old_password**: Текущий пароль
    - **new_password**: Новый пароль
    
    Требуется Bearer токен для авторизации
    """
    # Извлекаем токен из заголовка
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует токен авторизации")
    
    token = auth_header.replace("Bearer ", "")
    
    # Получаем данные из тела запроса
    try:
        body = await request.json()
        old_password = body.get("old_password")
        new_password = body.get("new_password")
        
        if not old_password or not new_password:
            raise HTTPException(status_code=400, detail="Требуются оба поля: old_password и new_password")
    except:
        raise HTTPException(status_code=400, detail="Неверный формат JSON")
    
    # Отправляем запрос в auth_service
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AUTH_SERVICE_URL}/auth/change-password",
            json={"old_password": old_password, "new_password": new_password},
            params={"token": token}
        )
        
        if response.status_code != 200:
            # Обрабатываем типичные ошибки
            if response.status_code == 400 and "Неверный текущий пароль" in response.text:
                raise HTTPException(status_code=400, detail="Неверный текущий пароль")
            elif response.status_code == 401:
                raise HTTPException(status_code=401, detail="Недействительный токен")
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            
            # Общая ошибка
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ошибка смены пароля: {response.text}"
            )
    
    return {"message": "Пароль успешно изменен"}

# Добавляем маршрут /auth/refresh для обратной совместимости
@app.post("/auth/refresh")
async def legacy_refresh(request: Request):
    """
    Обновление JWT токена
    
    Тело запроса (JSON):
    - **refresh_token**: Refresh токен
    """
    try:
        body = await request.json()
        refresh_token = body.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh токен обязателен")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/refresh",
                json={"refresh_token": refresh_token}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Ошибка обновления токена: {response.text}"
                )
            
            return response.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

# Добавляем маршрут /auth/change-password для обратной совместимости
@app.post("/auth/change-password")
async def legacy_change_password(request: Request):
    """
    Изменение пароля пользователя
    
    Тело запроса (JSON):
    - **old_password**: Текущий пароль
    - **new_password**: Новый пароль
    
    Авторизация: Требуется Bearer токен
    """
    # Извлекаем токен из заголовка
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует токен авторизации")
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        body = await request.json()
        old_password = body.get("old_password")
        new_password = body.get("new_password")
        
        if not old_password or not new_password:
            raise HTTPException(status_code=400, detail="Требуются оба поля: old_password и new_password")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/change-password",
                json={"old_password": old_password, "new_password": new_password},
                params={"token": token}
            )
            
            if response.status_code != 200:
                if response.status_code == 400 and "Неверный текущий пароль" in response.text:
                    raise HTTPException(status_code=400, detail="Неверный текущий пароль")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Ошибка смены пароля: {response.text}"
                )
        
        return {"message": "Пароль успешно изменен"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

# Для запуска сервиса напрямую через Python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

@app.get("/marketplace/products", tags=["Маркетплейс"])
async def get_marketplace_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    store: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    limit: int = 30
):
    """
    Получить список товаров с применением фильтров, сортировки и пагинации
    
    - **search**: Поиск по названию, бренду, категории
    - **category**: Фильтрация по категории товара
    - **brand**: Фильтрация по бренду товара
    - **store**: Фильтрация по маркетплейсу (ozon, wildberries, aliexpress, other)
    - **sort**: Сортировка (price-asc, price-desc, rating, discount)
    - **page**: Номер страницы (начинается с 1)
    - **limit**: Количество товаров на странице (по умолчанию 30)
    """
    
    # Создаем параметры запроса, исключая None значения
    params = {k: v for k, v in {
        'search': search,
        'category': category,
        'brand': brand,
        'store': store,
        'sort': sort,
        'page': page,
        'limit': limit
    }.items() if v is not None}
    
    # Получаем данные из кэша, если они там есть
    cache_key = f"marketplace_products_{search}_{category}_{brand}_{store}_{sort}_{page}_{limit}"
    cached_data = get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Если данных в кэше нет, делаем запрос к сервису
    try:
        response = requests.get(
            f"{MARKETPLACE_SERVICE_URL}/marketplace/products",
            params=params
        )
        data = handle_service_response(response, "Failed to get products from marketplace")
        
        # Кэшируем результат на 5 минут
        set_to_cache(cache_key, data, expire=300)
        
        return data
    except Exception as e:
        logger.error(f"Error getting marketplace products: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting marketplace products: {str(e)}")

@app.get("/marketplace/products/{product_id}", tags=["Маркетплейс"])
async def get_marketplace_product(product_id: int):
    """
    Получить детальную информацию о товаре по ID
    """
    
    # Получаем данные из кэша, если они там есть
    cache_key = f"marketplace_product_{product_id}"
    cached_data = get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Если данных в кэше нет, делаем запрос к сервису
    try:
        response = requests.get(
            f"{MARKETPLACE_SERVICE_URL}/marketplace/products/{product_id}"
        )
        data = handle_service_response(response, "Failed to get product from marketplace")
        
        # Кэшируем результат на 15 минут
        set_to_cache(cache_key, data, expire=900)
        
        return data
    except Exception as e:
        logger.error(f"Error getting marketplace product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting marketplace product: {str(e)}")

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    website: Optional[HttpUrl] = None
    logo_url: Optional[HttpUrl] = None

class ProductCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., gt=0)
    old_price: Optional[float] = Field(None, gt=0)
    discount: Optional[float] = Field(None, ge=0, le=100)
    image_url: HttpUrl
    category: str = Field(..., min_length=1, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    status: str = Field(..., pattern='^(В наличии|Нет в наличии|Распродажа)$')
    rating: Optional[float] = Field(None, ge=0, le=5)
    external_url: Optional[HttpUrl] = None
    store: str = Field(..., pattern='^(Ozon|Wildberries|Aliexpress|Другие)$')
    description: Optional[str] = Field(None, max_length=5000)
    company: Optional[CompanyBase] = None

    @validator('old_price')
    def old_price_must_be_greater_than_price(cls, v, values):
        if v is not None and 'price' in values and v <= values['price']:
            raise ValueError('old_price must be greater than price')
        return v

    @validator('discount')
    def validate_discount(cls, v, values):
        if v is not None and 'old_price' in values and 'price' in values:
            calculated_discount = ((values['old_price'] - values['price']) / values['old_price']) * 100
            if abs(v - calculated_discount) > 0.01:  # Учитываем погрешность округления
                raise ValueError('discount does not match price and old_price')
        return v

@app.post("/marketplace/products", tags=["Маркетплейс"])
async def create_marketplace_product(
    product: ProductCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Создать новый товар (требует аутентификации администратора)
    """
    # Проверяем права администратора
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if not response.json() or not response.json().get("is_admin", False):
            raise HTTPException(status_code=403, detail="Only administrators can add products")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Делаем запрос к сервису
    try:
        # Преобразуем модель в словарь и конвертируем HttpUrl в строки
        product_data = product.model_dump(exclude_none=True)
        
        # Преобразуем статус
        status_mapping = {
            "В наличии": "in-stock",
            "Нет в наличии": "out-of-stock",
            "Распродажа": "sale"
        }
        product_data["status"] = status_mapping.get(product_data["status"], "in-stock")
        
        # Преобразуем store
        store_mapping = {
            "Ozon": "ozon",
            "Wildberries": "wildberries",
            "Aliexpress": "aliexpress",
            "Другие": "other"
        }
        product_data["store"] = store_mapping.get(product_data["store"], "other")
        
        # Переименовываем image_url в image и преобразуем в строку
        if "image_url" in product_data:
            product_data["image"] = str(product_data["image_url"])
            del product_data["image_url"]
        
        # Преобразуем external_url в строку
        if "external_url" in product_data:
            product_data["external_url"] = str(product_data["external_url"])
        
        # Добавляем обязательные поля для company
        if "company" in product_data:
            company = product_data["company"]
            if "website" in company:
                company["website"] = str(company["website"])
            if "logo_url" in company:
                company["logo_url"] = str(company["logo_url"])
            
            # Добавляем обязательные поля, если их нет
            if "rating" not in company:
                company["rating"] = 0
            if "products_count" not in company:
                company["products_count"] = 0
            if "is_premium" not in company:
                company["is_premium"] = False
            if "has_ozon_delivery" not in company:
                company["has_ozon_delivery"] = False
            if "return_period" not in company:
                company["return_period"] = 14

        # Преобразуем все HttpUrl объекты в строки
        def convert_urls_to_strings(data):
            if isinstance(data, dict):
                return {k: convert_urls_to_strings(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [convert_urls_to_strings(item) for item in data]
            elif hasattr(data, 'url'):  # Проверяем, является ли объект HttpUrl
                return str(data)
            return data

        product_data = convert_urls_to_strings(product_data)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MARKETPLACE_SERVICE_URL}/marketplace/products",
                json=product_data,
                timeout=30.0
            )
            
            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
                
            data = response.json()
            
            # Инвалидируем кэш списка продуктов
            set_to_cache("marketplace_products_list", None, expire=1)
            
            return data
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Marketplace service timeout")
    except Exception as e:
        logger.error(f"Error creating marketplace product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating marketplace product: {str(e)}")
