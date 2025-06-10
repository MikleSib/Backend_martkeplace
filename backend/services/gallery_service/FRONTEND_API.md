# Gallery Service API - Документация для фронтенда

## Базовый URL
```
http://localhost:8010/api/v1
```

## Авторизация
Все защищенные эндпоинты требуют JWT токен в заголовке:
```
Authorization: Bearer {jwt_token}
```

---

## 📸 ГАЛЕРЕИ

### 1. Получить список галерей
```http
GET /galleries?page=1&page_size=12&author_id=123
```

**Параметры:**
- `page` (int, опционально) - номер страницы (по умолчанию 1)
- `page_size` (int, опционально) - размер страницы (по умолчанию 12, макс 50)
- `author_id` (int, опционально) - фильтр по автору

**Ответ 200:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Моя рыбалка",
      "author_id": 6,
      "created_at": "2025-01-20T10:30:00Z",
      "views_count": 150,
      "likes_count": 25,
      "dislikes_count": 2,
      "comments_count": 8,
      "preview_image": {
        "id": 101,
        "image_url": "/files/abc123-image1.jpg",
        "thumbnail_url": "/files/abc123-thumb1.jpg",
        "dimensions": "1920x1080",
        "size": 2048000,
        "order_index": 0,
        "created_at": "2025-01-20T10:30:00Z"
      },
      "author": {
        "id": 6,
        "username": "Никита007",
        "fullname": "Никита",
        "avatar": "/files/374211c0-avatar.jpg",
        "registration_date": "2025-01-06T08:13:01Z",
        "posts_count": 15,
        "role": "user"
      }
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 12,
  "pages": 4
}
```

### 2. Получить детали галереи
```http
GET /galleries/{gallery_id}
```

**Ответ 200:**
```json
{
  "id": 1,
  "title": "Моя рыбалка",
  "author_id": 6,
  "created_at": "2025-01-20T10:30:00Z",
  "updated_at": "2025-01-20T10:30:00Z",
  "views_count": 151,
  "likes_count": 25,
  "dislikes_count": 2,
  "comments_count": 8,
  "images": [
    {
      "id": 101,
      "image_url": "/files/abc123-image1.jpg",
      "thumbnail_url": "/files/abc123-thumb1.jpg",
      "dimensions": "1920x1080",
      "size": 2048000,
      "order_index": 0,
      "created_at": "2025-01-20T10:30:00Z"
    },
    {
      "id": 102,
      "image_url": "/files/def456-image2.jpg",
      "thumbnail_url": "/files/def456-thumb2.jpg",
      "dimensions": "1280x720",
      "size": 1024000,
      "order_index": 1,
      "created_at": "2025-01-20T10:31:00Z"
    }
  ],
  "author": {
    "id": 6,
    "username": "Никита007",
    "fullname": "Никита",
    "avatar": "/files/374211c0-avatar.jpg",
    "registration_date": "2025-01-06T08:13:01Z",
    "posts_count": 15,
    "role": "user"
  }
}
```

**Ошибка 404:**
```json
{
  "detail": "Галерея не найдена"
}
```

### 3. Создать галерею
```http
POST /galleries
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "title": "Моя рыбалка",
  "images": [
    {
      "image_url": "/files/abc123-image1.jpg",
      "thumbnail_url": "/files/abc123-thumb1.jpg",
      "dimensions": "1920x1080",
      "size": 2048000,
      "order_index": 0
    },
    {
      "image_url": "/files/def456-image2.jpg",
      "thumbnail_url": "/files/def456-thumb2.jpg",
      "dimensions": "1280x720",
      "size": 1024000,
      "order_index": 1
    }
  ]
}
```

**Ответ 201:** (такой же как GET /galleries/{id})

**Ошибки:**
- `400` - Неверные данные (минимум 1, максимум 5 изображений)
- `401` - Не авторизован

### 4. Обновить галерею
```http
PUT /galleries/{gallery_id}
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "title": "Новое название галереи"
}
```

**Ответ 200:** (такой же как GET /galleries/{id})

**Ошибки:**
- `403` - Нет прав (не владелец)
- `404` - Галерея не найдена

### 5. Удалить галерею
```http
DELETE /galleries/{gallery_id}
Authorization: Bearer {jwt_token}
```

**Ответ 204:** (пустое тело)

**Ошибки:**
- `403` - Нет прав (не владелец)
- `404` - Галерея не найдена

---

## 🖼️ ЗАГРУЗКА ИЗОБРАЖЕНИЙ

### Загрузить изображение
```http
POST /galleries/upload_image
Authorization: Bearer {jwt_token}
Content-Type: multipart/form-data
```

**Тело запроса:**
```
file: [binary data]
```

**Ответ 201:**
```json
{
  "image_url": "/files/abc123-original.jpg",
  "thumbnail_url": "/files/abc123-thumb.jpg",
  "size": 2048000,
  "dimensions": "1920x1080",
  "filename": "my_photo.jpg",
  "content_type": "image/jpeg"
}
```

**Ошибки:**
- `400` - Файл не является изображением
- `413` - Размер файла превышает 8MB
- `401` - Не авторизован

---

## 💬 КОММЕНТАРИИ

### 1. Получить комментарии
```http
GET /galleries/{gallery_id}/comments?page=1&page_size=20
```

**Ответ 200:**
```json
{
  "items": [
    {
      "id": 15,
      "gallery_id": 1,
      "author_id": 70,
      "content": "Отличные фотографии! Где это было снято?",
      "created_at": "2025-01-20T11:00:00Z",
      "updated_at": "2025-01-20T11:00:00Z",
      "is_edited": false,
      "author": {
        "id": 70,
        "username": "Рыбак_Про",
        "fullname": "Сергей",
        "avatar": "/files/user70-avatar.jpg",
        "registration_date": "2024-05-15T09:00:00Z",
        "posts_count": 25,
        "role": "user"
      }
    }
  ],
  "total": 8,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

### 2. Добавить комментарий
```http
POST /galleries/{gallery_id}/comments
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "content": "Отличные фотографии! Где это было снято?"
}
```

**Ответ 201:**
```json
{
  "id": 15,
  "gallery_id": 1,
  "author_id": 70,
  "content": "Отличные фотографии! Где это было снято?",
  "created_at": "2025-01-20T11:00:00Z",
  "updated_at": "2025-01-20T11:00:00Z",
  "is_edited": false,
  "author": {
    "id": 70,
    "username": "Рыбак_Про",
    "fullname": "Сергей",
    "avatar": "/files/user70-avatar.jpg",
    "registration_date": "2024-05-15T09:00:00Z",
    "posts_count": 25,
    "role": "user"
  }
}
```

### 3. Обновить комментарий
```http
PUT /galleries/{gallery_id}/comments/{comment_id}
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "content": "Исправленный текст комментария"
}
```

**Ответ 200:** (такой же как при создании, но `is_edited: true`)

### 4. Удалить комментарий
```http
DELETE /galleries/{gallery_id}/comments/{comment_id}
Authorization: Bearer {jwt_token}
```

**Ответ 204:** (пустое тело)

---

## 👍 РЕАКЦИИ

### 1. Поставить лайк
```http
POST /galleries/{gallery_id}/like
Authorization: Bearer {jwt_token}
```

**Ответ 200:**
```json
{
  "message": "Лайк успешно добавлен"
}
```

**Ошибка 400:**
```json
{
  "detail": "Вы уже поставили лайк этой галерее"
}
```

### 2. Поставить дизлайк
```http
POST /galleries/{gallery_id}/dislike
Authorization: Bearer {jwt_token}
```

**Ответ 200:**
```json
{
  "message": "Дизлайк успешно добавлен"
}
```

### 3. Убрать реакцию
```http
DELETE /galleries/{gallery_id}/reactions
Authorization: Bearer {jwt_token}
```

**Ответ 200:**
```json
{
  "message": "Реакция успешно удалена"
}
```

---

## 🔧 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Пример 1: Загрузка и создание галереи

**1. Загружаем изображения:**
```javascript
const uploadImage = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('/api/v1/galleries/upload_image', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  
  return await response.json();
};
```

**2. Создаем галерею:**
```javascript
const createGallery = async (title, uploadedImages) => {
  const images = uploadedImages.map((img, index) => ({
    image_url: img.image_url,
    thumbnail_url: img.thumbnail_url,
    dimensions: img.dimensions,
    size: img.size,
    order_index: index
  }));

  const response = await fetch('/api/v1/galleries', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      title: title,
      images: images
    })
  });
  
  return await response.json();
};
```

### Пример 2: Получение галерей с пагинацией

```javascript
const getGalleries = async (page = 1, authorId = null) => {
  let url = `/api/v1/galleries?page=${page}&page_size=12`;
  if (authorId) {
    url += `&author_id=${authorId}`;
  }
  
  const response = await fetch(url);
  return await response.json();
};
```

### Пример 3: Работа с комментариями

```javascript
const addComment = async (galleryId, content) => {
  const response = await fetch(`/api/v1/galleries/${galleryId}/comments`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ content })
  });
  
  return await response.json();
};
```

---

## ⚠️ ВАЖНЫЕ МОМЕНТЫ

1. **Изображения в порядке** - используйте `order_index` для правильного отображения
2. **Превью и детали** - в списке только первое изображение, в деталях все
3. **Счетчики автоматические** - при просмотре деталей `views_count` увеличивается
4. **Реакции взаимоисключающие** - лайк заменяет дизлайк и наоборот
5. **Права доступа** - редактировать/удалять может только владелец
6. **Лимиты** - максимум 5 изображений в галерее, 8MB на изображение 