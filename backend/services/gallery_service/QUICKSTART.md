# Быстрый старт - Система фотогалерей

## Описание
Система фотогалерей позволяет пользователям создавать и делиться коллекциями изображений с функциями комментирования и реакций.

## Основные возможности
- ✅ Создание галерей с до 5 изображениями (требует регистрации)
- ✅ Пагинированный просмотр (12 галерей на страницу) **для всех**
- ✅ Детальный просмотр с полными изображениями **для всех**
- ✅ Система комментариев с пагинацией (просмотр для всех, создание для зарегистрированных)
- ✅ Лайки и дизлайки для галерей (требует регистрации)
- ✅ Автоматические счетчики просмотров
- ✅ Интеграция с user_service для данных пользователей

## Архитектура
- **Порт**: 8010
- **База данных**: PostgreSQL (порт 5438)
- **Аутентификация**: JWT через auth_service
- **Файлы**: Интеграция с file_service (лимит 8MB)

## Быстрый тест

### 1. Запуск системы
```bash
docker-compose up gallery_service db_gallery
```

### 2. Создание галереи
```bash
# Сначала получите токен аутентификации
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"password"}'

# Создайте галерею
curl -X POST http://localhost:8000/galleries \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Моя первая галерея",
    "description": "Описание галереи",
    "images": [
      {
        "image_url": "/uploads/image1.jpg",
        "thumbnail_url": "/uploads/thumb_image1.jpg",
        "size": 1024000,
        "order_index": 0
      }
    ]
  }'
```

### 3. Просмотр галерей (БЕЗ ТОКЕНА - доступно всем)
```bash
# Список галерей
curl http://localhost:8000/galleries?page=1&page_size=12

# Детальный просмотр (автоматически увеличивает счетчик просмотров)
curl http://localhost:8000/galleries/1

# Комментарии к галерее  
curl http://localhost:8000/galleries/1/comments?page=1&page_size=20
```

### 4. Добавление комментария (ТРЕБУЕТ ТОКЕН)
```bash
curl -X POST http://localhost:8000/galleries/1/comments \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Отличная галерея!"}'
```

### 5. Реакции (ТРЕБУЕТ ТОКЕН)
```bash
# Лайк
curl -X POST http://localhost:8000/galleries/1/like \
  -H "Authorization: Bearer YOUR_TOKEN"

# Дизлайк  
curl -X POST http://localhost:8000/galleries/1/dislike \
  -H "Authorization: Bearer YOUR_TOKEN"

# Удаление реакции
curl -X DELETE http://localhost:8000/galleries/1/reactions \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Интеграция с фронтендом

### JavaScript пример
```javascript
// Получение галерей
async function getGalleries(page = 1) {
    const response = await fetch(`/galleries?page=${page}&page_size=12`);
    return await response.json();
}

// Создание галереи
async function createGallery(galleryData, token) {
    const response = await fetch('/galleries', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(galleryData)
    });
    return await response.json();
}

// Лайк галереи
async function likeGallery(galleryId, token) {
    const response = await fetch(`/galleries/${galleryId}/like`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    return await response.json();
}
```

## Структура данных

### Галерея (список)
```json
{
    "id": 1,
    "title": "Название галереи",
    "description": "Описание",
    "author_id": 123,
    "author_username": "username",
    "created_at": "2024-01-01T00:00:00",
    "views_count": 150,
    "likes_count": 25,
    "dislikes_count": 2,
    "comments_count": 10,
    "images_count": 3,
    "preview_image": {
        "image_url": "/uploads/image.jpg",
        "thumbnail_url": "/uploads/thumb.jpg"
    }
}
```

### Галерея (детальная)
```json
{
    "id": 1,
    "title": "Название галереи", 
    "description": "Описание",
    "author": {
        "id": 123,
        "username": "username",
        "avatar": "/uploads/avatar.jpg"
    },
    "images": [
        {
            "id": 1,
            "image_url": "/uploads/image1.jpg",
            "thumbnail_url": "/uploads/thumb1.jpg",
            "size": 1024000,
            "order_index": 0
        }
    ],
    "created_at": "2024-01-01T00:00:00",
    "views_count": 150,
    "likes_count": 25,
    "dislikes_count": 2,
    "comments_count": 10
}
```

## Технические ограничения
- Максимум 5 изображений на галерею
- Размер файла до 8MB
- Поддерживаемые форматы: JPG, PNG, GIF, WebP
- Пагинация: до 50 элементов на страницу
- Комментарии: до 1000 символов

## Мониторинг
```bash
# Проверка здоровья сервиса
curl http://localhost:8010/health

# Swagger документация
http://localhost:8010/docs
```

Система готова к использованию! 🎉 