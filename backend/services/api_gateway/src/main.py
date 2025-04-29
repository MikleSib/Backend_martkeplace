import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import requests
from .config import *
import logging

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
    user_id: int = Depends(verify_token)
):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        user_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{user_id}")
        if user_response.status_code != 200:
            raise HTTPException(status_code=404, detail="User profile not found")
        user_info = user_response.json()
        
        post_data = {
            "title": title,
            "content": content,
            "author_id": user_id,
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
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error creating post"))
            
        return {"message": "Post created successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/post/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    cache_key = f"post_{post_id}"
    cached_post = get_from_cache(cache_key)
    if cached_post:
        logger.info(f"Post {post_id} found in cache")
        return cached_post

    try:
        response = requests.get(f"{POST_SERVICE_URL}/posts/{post_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting post"))
        
        post_data = response.json()
        set_to_cache(cache_key, post_data)
        logger.info(f"Post {post_id} saved to cache")
        
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
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error getting posts"))
            
        posts = response.json()
        
        for post in posts:
            author_response = requests.get(f"{USER_SERVICE_URL}/user/profile/{post['author_id']}")
            if author_response.status_code == 200:
                post['author'] = author_response.json()
            else:
                post['author'] = {
                    "id": post['author_id'],
                    "username": "[Удаленный пользователь]",
                    "full_name": "[Удаленный пользователь]",
                    "about_me": None
                }
                
        return posts
    except Exception as e:
        logger.error(f"Error getting posts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/post/{post_id}", response_model=PostResponse)
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

        cache_key = f"post_{post_id}"
        set_to_cache(cache_key, None, expire=0)
        
        return response.json()
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/post/{post_id}")
async def delete_post(post_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/posts/{post_id}",
            params={"author_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting post"))
        
        cache_key = f"post_{post_id}"
        set_to_cache(cache_key, None, expire=0)
        
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/post/{post_id}/comment", response_model=CommentResponse)
async def create_comment(post_id: int, comment_data: CommentCreate, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/comments"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.post(
            f"{POST_SERVICE_URL}/posts/{post_id}/comments/",
            json={**comment_data.dict(), "author_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error creating comment"))

        cache_key = f"post_{post_id}"
        set_to_cache(cache_key, None, expire=0)
        
        return response.json()
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
        return response.json()
    except Exception as e:
        logger.error(f"Error getting comments for post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/comment/{comment_id}", response_model=CommentResponse)
async def update_comment(comment_id: int, comment_data: CommentUpdate, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/comments/{comment_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.patch(
            f"{POST_SERVICE_URL}/comments/{comment_id}",
            json=comment_data.dict(),
            params={"author_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error updating comment"))
        return response.json()
    except Exception as e:
        logger.error(f"Error updating comment {comment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/comment/{comment_id}")
async def delete_comment(comment_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/comments/{comment_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/comments/{comment_id}",
            params={"author_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error deleting comment"))
        return response.json()
    except Exception as e:
        logger.error(f"Error deleting comment {comment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/post/{post_id}/like", response_model=LikeResponse)
async def add_like(post_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/likes"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.post(
            f"{POST_SERVICE_URL}/posts/{post_id}/likes/",
            json={"user_id": user_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error adding like"))
        
        cache_key = f"post_{post_id}"
        set_to_cache(cache_key, None, expire=0)
        
        return response.json()
    except Exception as e:
        logger.error(f"Error adding like to post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/post/{post_id}/like")
async def remove_like(post_id: int, user_id: int = Depends(verify_token)):
    if not check_route_enabled(f"{POST_SERVICE_URL}/posts/{post_id}/likes/{user_id}"):
        raise HTTPException(status_code=503, detail="Post service is not running")
    
    try:
        response = requests.delete(
            f"{POST_SERVICE_URL}/posts/{post_id}/likes/{user_id}"
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Error removing like"))
        
        cache_key = f"post_{post_id}"
        set_to_cache(cache_key, None, expire=0)
        
        return response.json()
    except Exception as e:
        logger.error(f"Error removing like from post {post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
