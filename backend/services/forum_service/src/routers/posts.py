from datetime import datetime
from typing import List, Optional
import os

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
import httpx
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.database import get_db
from database.models import Category, NotificationType, Post, ReferenceType, Topic, Image
from src.schemas.common import MessageResponse, PaginatedResponse
from src.schemas.post import PostCreate, PostDetailResponse, PostResponse, PostUpdate, UserInfo
from src.utils.auth import User, get_current_user
from src.utils.dependencies import (check_post_owner_or_moderator, get_post_or_404,
                                 get_topic_or_404)
from src.utils.pagination import paginate

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("/{post_id}", response_model=PostDetailResponse)
async def get_post(
    post: Post = Depends(get_post_or_404),
    db: AsyncSession = Depends(get_db)
):
    """Получение подробной информации о сообщении"""
    # Получаем данные автора из user_service
    author_data = {
        "username": "Неизвестный",
        "avatar": None,
        "signature": None,
        "post_count": 0
    }
    
    user_info = None
    quoted_post_user = None
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.USER_SERVICE_URL}/users/{post.author_id}"
            )
            if response.status_code == 200:
                user_data = response.json()
                author_data = {
                    "username": user_data.get("username", "Неизвестный"),
                    "avatar": user_data.get("avatar"),
                    "signature": user_data.get("signature"),
                    "post_count": user_data.get("posts_count", 0)
                }
                
                # Создаем полный объект информации о пользователе
                user_info = UserInfo(
                    id=post.author_id,
                    username=user_data.get("username", "Неизвестный"),
                    fullname=user_data.get("full_name"),
                    avatar=user_data.get("avatar"),
                    registration_date=user_data.get("registration_date"),
                    posts_count=user_data.get("posts_count", 0),
                    role=user_data.get("role", "user")
                )
    except httpx.RequestError:
        # В случае ошибки используем дефолтные данные
        pass
    
    # Получаем изображения сообщения
    images_query = select(post.images)
    images_result = await db.execute(images_query)
    images = images_result.scalars().all()
    
    # Получаем информацию о цитируемом сообщении, если есть
    quoted_content = None
    quoted_author = None
    
    if post.quoted_post_id:
        quoted_post_query = select(Post).where(Post.id == post.quoted_post_id)
        quoted_post = await db.scalar(quoted_post_query)
        
        if quoted_post:
            quoted_content = quoted_post.content[:200] + "..." if len(quoted_post.content) > 200 else quoted_post.content
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.USER_SERVICE_URL}/users/{quoted_post.author_id}"
                    )
                    if response.status_code == 200:
                        quoted_user_data = response.json()
                        quoted_author = quoted_user_data.get("username", "Неизвестный")
                        
                        # Создаем полный объект информации о пользователе цитируемого сообщения
                        quoted_post_user = UserInfo(
                            id=quoted_post.author_id,
                            username=quoted_user_data.get("username", "Неизвестный"),
                            fullname=quoted_user_data.get("full_name"),
                            avatar=quoted_user_data.get("avatar"),
                            registration_date=quoted_user_data.get("registration_date"),
                            posts_count=quoted_user_data.get("posts_count", 0),
                            role=quoted_user_data.get("role", "user")
                        )
            except httpx.RequestError:
                quoted_author = "Неизвестный"
    
    # Формируем ответ
    result = PostDetailResponse(
        **post.__dict__,
        author_username=author_data["username"],
        author_avatar=author_data["avatar"],
        author_signature=author_data["signature"],
        author_post_count=author_data["post_count"],
        user=user_info,
        images=images,
        quoted_content=quoted_content,
        quoted_author=quoted_author,
        quoted_post_user=quoted_post_user
    )
    
    return result

@router.get("", response_model=PaginatedResponse[PostResponse])
async def get_posts(
    topic_id: int = Query(..., description="ID темы"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка сообщений в теме с пагинацией"""
    # Проверяем существование темы
    topic_query = select(Topic).where(Topic.id == topic_id, Topic.is_deleted == False)
    topic = await db.scalar(topic_query)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Тема с ID {topic_id} не найдена"
        )
    
    # Получаем сообщения с пагинацией
    posts_query = select(Post).where(
        Post.topic_id == topic_id,
        Post.is_deleted == False
    ).order_by(Post.created_at)
    
    # Применяем пагинацию
    pagination_result = await paginate(db, posts_query, page, page_size)
    posts = pagination_result["items"]
    
    # Получаем идентификаторы авторов сообщений
    author_ids = [post.author_id for post in posts]
    
    # Получаем информацию о пользователях из user_service
    users_by_id = {}
    if author_ids:
        try:
            async with httpx.AsyncClient() as client:
                # Сначала пробуем групповой запрос, если такой метод доступен
                response = await client.post(
                    f"{settings.USER_SERVICE_URL}/users/batch",
                    json={"user_ids": author_ids}
                )
                
                if response.status_code == 200:
                    users_data = response.json()
                    for user_data in users_data:
                        users_by_id[user_data["id"]] = UserInfo(
                            id=user_data["id"],
                            username=user_data.get("username", "Неизвестный"),
                            fullname=user_data.get("full_name"),
                            avatar=user_data.get("avatar"),
                            registration_date=user_data.get("registration_date"),
                            posts_count=user_data.get("posts_count", 0),
                            role=user_data.get("role", "user")
                        )
                else:
                    # Если групповой запрос не поддерживается, делаем отдельные запросы
                    for author_id in set(author_ids):
                        user_response = await client.get(f"{settings.USER_SERVICE_URL}/users/{author_id}")
                        if user_response.status_code == 200:
                            user_data = user_response.json()
                            users_by_id[author_id] = UserInfo(
                                id=author_id,
                                username=user_data.get("username", "Неизвестный"),
                                fullname=user_data.get("full_name"),
                                avatar=user_data.get("avatar"),
                                registration_date=user_data.get("registration_date"),
                                posts_count=user_data.get("posts_count", 0),
                                role=user_data.get("role", "user")
                            )
        except httpx.RequestError as e:
            # Логируем ошибку, но продолжаем работу
            print(f"Ошибка при получении данных пользователей: {str(e)}")
    
    # Объединяем данные сообщений с данными пользователей
    enhanced_posts = []
    for post in posts:
        post_dict = post.__dict__.copy()
        
        # Добавляем данные о пользователе, если доступны
        if post.author_id in users_by_id:
            post_dict["user"] = users_by_id[post.author_id]
        
        # Загружаем изображения для поста
        images_query = select(Image).where(Image.post_id == post.id)
        images_result = await db.execute(images_query)
        images = images_result.scalars().all()
        print(f"Загружено {len(images)} изображений для поста {post.id}")
        if images:
            for img in images:
                print(f"  - Изображение: ID {img.id}, URL: {img.image_url}")
        
        # Преобразуем ORM объекты в словари для правильной сериализации
        image_dicts = []
        for img in images:
            image_dicts.append({
                "id": img.id,
                "image_url": img.image_url,
                "thumbnail_url": img.thumbnail_url,
                "dimensions": img.dimensions
            })
        
        post_dict["images"] = image_dicts
        
        enhanced_posts.append(post_dict)
    
    # Формируем ответ
    response = PaginatedResponse[PostResponse](
        items=enhanced_posts,
        total=pagination_result["total"],
        page=pagination_result["page"],
        page_size=pagination_result["page_size"],
        pages=pagination_result["pages"]
    )
    print(f"Возвращаем {len(response.items)} постов")
    return response

@router.post("/upload_image", status_code=status.HTTP_201_CREATED)
async def upload_post_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Загрузка изображения для сообщения форума через файловый сервис"""
    try:
        # Проверяем MIME тип файла
        content_type = file.content_type.lower()
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Загружаемый файл должен быть изображением"
            )
            
        # Ограничение размера файла (например, 5MB)
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
        
        # Вместо чтения всего файла в память, откроем его как поток
        # Отправляем файл на сервис файлов напрямую
        async with httpx.AsyncClient() as client:
            # Получаем данные из потока
            file_content = await file.read()
            
            # Проверяем размер файла
            file_size = len(file_content)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Размер файла превышает максимально допустимый (5MB)"
                )
                
            # Перематываем файл в начало
            await file.seek(0)
            
            # Отправляем файл
            files = {"file": (file.filename, file.file, file.content_type)}
            response = await client.post(
                f"{settings.FILE_SERVICE_URL}/upload",
                files=files
            )
            
            if response.status_code != 200 and response.status_code != 201:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Ошибка при загрузке файла на сервер: {response.text}"
                )
                
            file_data = response.json()
                
            # Получаем размеры изображения, если возможно
            dimensions = None
            try:
                from PIL import Image as PILImage
                from io import BytesIO
                
                img = PILImage.open(BytesIO(file_content))
                dimensions = f"{img.width}x{img.height}"
            except Exception as e:
                # Игнорируем ошибки получения размеров
                print(f"Ошибка при получении размеров изображения: {str(e)}")
                
            # Формируем и возвращаем данные для создания сообщения
            return {
                "image_url": file_data["url"],
                "thumbnail_url": file_data.get("thumbnail_url", file_data["url"]),
                "size": file_data["size"],
                "dimensions": dimensions,
                "filename": file_data["filename"],
                "content_type": file.content_type
            }
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при взаимодействии с файловым сервисом: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Произошла ошибка при загрузке изображения: {str(e)}"
        )

@router.post("", response_model=PostDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создание нового сообщения в теме"""
    # Проверяем существование темы
    topic_query = select(Topic).where(
        Topic.id == post_data.topic_id,
        Topic.is_deleted == False
    )
    topic = await db.scalar(topic_query)
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Тема с ID {post_data.topic_id} не найдена"
        )
    
    # Проверяем, что тема не закрыта
    if topic.is_closed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя добавлять сообщения в закрытую тему"
        )
    
    # Проверяем цитируемое сообщение, если указано
    if post_data.quoted_post_id:
        quoted_post_query = select(Post).where(
            Post.id == post_data.quoted_post_id,
            Post.is_deleted == False
        )
        quoted_post = await db.scalar(quoted_post_query)
        
        if not quoted_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Цитируемое сообщение с ID {post_data.quoted_post_id} не найдено"
            )
    
    # Создаем новое сообщение
    new_post = Post(
        topic_id=post_data.topic_id,
        author_id=current_user.id,
        content=post_data.content,
        quoted_post_id=post_data.quoted_post_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(new_post)
    await db.flush()
    
    # Обрабатываем изображения, если они есть
    post_images = []
    if post_data.images and len(post_data.images) > 0:
        print(f"Обработка изображений: получено {len(post_data.images)} изображений")
        for img_data in post_data.images:
            # Создаем объект изображения в БД
            print(f"Сохраняем изображение: {img_data.image_url}")
            image = Image(
                post_id=new_post.id,
                author_id=current_user.id,
                image_url=img_data.image_url,
                thumbnail_url=img_data.thumbnail_url,
                size=img_data.size if img_data.size is not None else 0,
                dimensions=img_data.dimensions,
                created_at=datetime.utcnow()
            )
            db.add(image)
            post_images.append(image)
        
        # Сохраняем изображения в базе данных
        await db.flush()
        print(f"Изображения сохранены. ID поста: {new_post.id}, количество: {len(post_images)}")
    
    # Обновляем счетчики и данные в теме
    topic.posts_count += 1
    topic.last_post_id = new_post.id
    topic.last_post_author_id = current_user.id
    topic.last_post_date = datetime.utcnow()
    
    # Обновляем счетчики в категории
    category_query = select(Category).where(Category.id == topic.category_id)
    category = await db.scalar(category_query)
    if category:
        category.messages_count += 1
    
    # Если это цитирование, создаем уведомление
    if post_data.quoted_post_id:
        # Получаем автора цитируемого сообщения
        quoted_post_query = select(Post).where(Post.id == post_data.quoted_post_id)
        quoted_post = await db.scalar(quoted_post_query)
        
        if quoted_post and quoted_post.author_id != current_user.id:
            # Создаем уведомление через API уведомлений
            try:
                notification_data = {
                    "user_id": quoted_post.author_id,
                    "sender_id": current_user.id,
                    "type": NotificationType.QUOTE.value,
                    "content": post_data.content[:100] + "..." if len(post_data.content) > 100 else post_data.content,
                    "reference_id": new_post.id,
                    "reference_type": ReferenceType.POST.value
                }
                
                # Здесь должен быть вызов сервиса уведомлений
                # Это заглушка для примера
                pass
            except Exception as e:
                # Игнорируем ошибки создания уведомления
                pass
    
    await db.commit()
    await db.refresh(new_post)
    
    # Создаем объект информации о пользователе
    user_info = UserInfo(
        id=current_user.id,
        username=current_user.username,
        fullname=getattr(current_user, "fullname", None),
        avatar=None,  # Получаем из user_service, если возможно
        registration_date=None,  # Получаем из user_service, если возможно
        posts_count=0,  # Получаем из user_service, если возможно
        role=current_user.role
    )
    
    # Пытаемся получить дополнительные данные из user_service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.USER_SERVICE_URL}/users/{current_user.id}"
            )
            if response.status_code == 200:
                user_data = response.json()
                user_info = UserInfo(
                    id=current_user.id,
                    username=current_user.username,
                    fullname=user_data.get("full_name"),
                    avatar=user_data.get("avatar"),
                    registration_date=user_data.get("registration_date"),
                    posts_count=user_data.get("posts_count", 0),
                    role=current_user.role
                )
    except httpx.RequestError:
        # Игнорируем ошибки получения данных пользователя
        pass
    
    # Формируем ответ
    result = PostDetailResponse(
        **new_post.__dict__,
        author_username=current_user.username,
        author_avatar=user_info.avatar,
        author_signature=None,
        author_post_count=user_info.posts_count,
        user=user_info,
        images=post_images,
        quoted_content=None,
        quoted_author=None,
        quoted_post_user=None
    )
    
    # Если есть цитируемое сообщение, получаем его данные
    if post_data.quoted_post_id:
        quoted_post = await db.scalar(select(Post).where(Post.id == post_data.quoted_post_id))
        if quoted_post:
            result.quoted_content = quoted_post.content[:200] + "..." if len(quoted_post.content) > 200 else quoted_post.content
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.USER_SERVICE_URL}/users/{quoted_post.author_id}"
                    )
                    if response.status_code == 200:
                        quoted_user_data = response.json()
                        result.quoted_author = quoted_user_data.get("username", "Неизвестный")
                        
                        result.quoted_post_user = UserInfo(
                            id=quoted_post.author_id,
                            username=quoted_user_data.get("username", "Неизвестный"),
                            fullname=quoted_user_data.get("full_name"),
                            avatar=quoted_user_data.get("avatar"),
                            registration_date=quoted_user_data.get("registration_date"),
                            posts_count=quoted_user_data.get("posts_count", 0),
                            role=quoted_user_data.get("role", "user")
                        )
            except httpx.RequestError:
                result.quoted_author = "Неизвестный"
    
    return result

@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_data: PostUpdate,
    post: Post = Depends(check_post_owner_or_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Обновление сообщения (владельцем или модератором)"""
    # Проверяем, что сообщение не является стартовым сообщением темы
    if post.is_topic_starter:
        # Для стартового сообщения нужно обновлять и тему тоже
        # Это может быть реализовано через другой эндпоинт
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для редактирования первого сообщения темы используйте API редактирования темы"
        )
    
    # Обновляем данные сообщения
    if post_data.content is not None:
        post.content = post_data.content
        post.is_edited = True
        post.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(post)
    
    return post

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post: Post = Depends(check_post_owner_or_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Удаление сообщения (владельцем или модератором)"""
    # Проверяем, что сообщение не является стартовым сообщением темы
    if post.is_topic_starter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для удаления первого сообщения удалите всю тему"
        )
    
    # Логическое удаление сообщения
    post.is_deleted = True
    
    # Получаем тему для обновления счетчиков
    topic_query = select(Topic).where(Topic.id == post.topic_id)
    topic = await db.scalar(topic_query)
    
    if topic:
        # Уменьшаем счетчик сообщений
        topic.posts_count = max(0, topic.posts_count - 1)
        
        # Если это было последнее сообщение, обновляем last_post_id
        if topic.last_post_id == post.id:
            # Находим предыдущее неудаленное сообщение
            prev_post_query = select(Post).where(
                Post.topic_id == topic.id,
                Post.is_deleted == False,
                Post.id != post.id
            ).order_by(desc(Post.created_at)).limit(1)
            
            prev_post = await db.scalar(prev_post_query)
            
            if prev_post:
                topic.last_post_id = prev_post.id
                topic.last_post_author_id = prev_post.author_id
                topic.last_post_date = prev_post.created_at
        
        # Обновляем счетчики в категории
        category_query = select(Category).where(Category.id == topic.category_id)
        category = await db.scalar(category_query)
        if category:
            category.messages_count = max(0, category.messages_count - 1)
    
    await db.commit()
    
    return None

@router.post("/{post_id}/like", response_model=MessageResponse)
async def like_post(
    post: Post = Depends(get_post_or_404),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Лайк сообщения"""
    # Проверяем, что пользователь еще не лайкал это сообщение
    reaction_query = select(post.reactions).where(
        post.reactions.any(user_id=current_user.id)
    )
    reaction = await db.scalar(reaction_query)
    
    if reaction:
        # Уже есть реакция, это обновление
        if reaction.type == "like":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вы уже поставили лайк этому сообщению"
            )
        
        # Меняем дизлайк на лайк
        reaction.type = "like"
        post.likes_count += 1
        post.dislikes_count = max(0, post.dislikes_count - 1)
    else:
        # Создаем новую реакцию
        from database.models import Reaction, ReactionType
        
        new_reaction = Reaction(
            post_id=post.id,
            user_id=current_user.id,
            type=ReactionType.LIKE,
            created_at=datetime.utcnow()
        )
        
        db.add(new_reaction)
        post.likes_count += 1
    
    # Создаем уведомление о лайке, если автор - не текущий пользователь
    if post.author_id != current_user.id:
        # Здесь должен быть вызов сервиса уведомлений
        # Это заглушка для примера
        pass
    
    await db.commit()
    
    return MessageResponse(message="Лайк успешно добавлен")

@router.post("/{post_id}/dislike", response_model=MessageResponse)
async def dislike_post(
    post: Post = Depends(get_post_or_404),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Дизлайк сообщения"""
    # Проверяем, что пользователь еще не дизлайкал это сообщение
    reaction_query = select(post.reactions).where(
        post.reactions.any(user_id=current_user.id)
    )
    reaction = await db.scalar(reaction_query)
    
    if reaction:
        # Уже есть реакция, это обновление
        if reaction.type == "dislike":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вы уже поставили дизлайк этому сообщению"
            )
        
        # Меняем лайк на дизлайк
        reaction.type = "dislike"
        post.dislikes_count += 1
        post.likes_count = max(0, post.likes_count - 1)
    else:
        # Создаем новую реакцию
        from database.models import Reaction, ReactionType
        
        new_reaction = Reaction(
            post_id=post.id,
            user_id=current_user.id,
            type=ReactionType.DISLIKE,
            created_at=datetime.utcnow()
        )
        
        db.add(new_reaction)
        post.dislikes_count += 1
    
    await db.commit()
    
    return MessageResponse(message="Дизлайк успешно добавлен")

@router.delete("/{post_id}/reactions", response_model=MessageResponse)
async def remove_reaction(
    post: Post = Depends(get_post_or_404),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удаление реакции пользователя на сообщение"""
    # Проверяем, есть ли реакция пользователя на это сообщение
    from database.models import Reaction
    
    reaction_query = select(Reaction).where(
        Reaction.post_id == post.id,
        Reaction.user_id == current_user.id
    )
    
    reaction = await db.scalar(reaction_query)
    
    if not reaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Реакция не найдена"
        )
    
    # Обновляем счетчики в зависимости от типа реакции
    if reaction.type == "like":
        post.likes_count = max(0, post.likes_count - 1)
    else:
        post.dislikes_count = max(0, post.dislikes_count - 1)
    
    # Удаляем реакцию
    await db.delete(reaction)
    await db.commit()
    
    return MessageResponse(message="Реакция успешно удалена") 