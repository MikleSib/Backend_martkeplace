# Gallery Service - Сервис фотогалерей

## Описание
Сервис для управления фотогалереями с возможностью загрузки до 5 изображений, комментариями и реакциями.

## Основные возможности
- Создание фотогалерей с названием и до 5 изображений
- Просмотр списка галерей с пагинацией (показывается только первое изображение)
- Детальный просмотр галереи со всеми изображениями
- Система комментариев к галереям
- Система лайков/дизлайков
- Счетчики просмотров, комментариев и реакций

## API Endpoints

### Галереи

#### GET /api/v1/galleries
Получение списка галерей с пагинацией
- Query параметры:
  - `page` (int): Номер страницы (по умолчанию 1)
  - `page_size` (int): Размер страницы (по умолчанию 12, макс 50)
  - `author_id` (int, опционально): Фильтр по автору
- Ответ: Список галерей с превью изображениями

#### POST /api/v1/galleries
Создание новой галереи
- Требует авторизации
- Тело запроса:
```json
{
  "title": "Название галереи",
  "images": [
    {
      "image_url": "https://example.com/image1.jpg",
      "thumbnail_url": "https://example.com/thumb1.jpg",
      "dimensions": "1920x1080",
      "size": 1024000,
      "order_index": 0
    }
  ]
}
```

#### GET /api/v1/galleries/{gallery_id}
Получение детальной информации о галерее
- Автоматически увеличивает счетчик просмотров
- Возвращает все изображения галереи

#### PUT /api/v1/galleries/{gallery_id}
Обновление галереи (только владельцем)
- Требует авторизации
- Можно изменить только название

#### DELETE /api/v1/galleries/{gallery_id}
Удаление галереи (только владельцем)
- Требует авторизации
- Логическое удаление

### Изображения

#### POST /api/v1/galleries/upload_image
Загрузка изображения для галереи
- Требует авторизации
- Формат: multipart/form-data
- Максимальный размер: 8MB
- Поддерживаемые форматы: все изображения

### Комментарии

#### GET /api/v1/galleries/{gallery_id}/comments
Получение комментариев к галерее
- Query параметры:
  - `page` (int): Номер страницы
  - `page_size` (int): Размер страницы (макс 100)

#### POST /api/v1/galleries/{gallery_id}/comments
Создание комментария
- Требует авторизации
- Тело запроса:
```json
{
  "content": "Текст комментария"
}
```

#### PUT /api/v1/galleries/{gallery_id}/comments/{comment_id}
Обновление комментария (только автором)
- Требует авторизации

#### DELETE /api/v1/galleries/{gallery_id}/comments/{comment_id}
Удаление комментария (только автором)
- Требует авторизации

### Реакции

#### POST /api/v1/galleries/{gallery_id}/like
Поставить лайк галерее
- Требует авторизации
- Если уже есть дизлайк - меняет на лайк

#### POST /api/v1/galleries/{gallery_id}/dislike
Поставить дизлайк галерее
- Требует авторизации
- Если уже есть лайк - меняет на дизлайк

#### DELETE /api/v1/galleries/{gallery_id}/reactions
Удалить реакцию пользователя
- Требует авторизации

## Схемы данных

### GalleryPreview (для списка)
```json
{
  "id": 1,
  "title": "Название галереи",
  "author_id": 123,
  "created_at": "2023-12-01T10:00:00Z",
  "views_count": 150,
  "likes_count": 25,
  "dislikes_count": 2,
  "comments_count": 8,
  "preview_image": {
    "id": 1,
    "image_url": "https://example.com/image.jpg",
    "thumbnail_url": "https://example.com/thumb.jpg",
    "dimensions": "1920x1080",
    "size": 1024000,
    "order_index": 0,
    "created_at": "2023-12-01T10:00:00Z"
  },
  "author": {
    "id": 123,
    "username": "user123",
    "fullname": "Иван Иванов",
    "avatar": "https://example.com/avatar.jpg",
    "posts_count": 50,
    "role": "user"
  }
}
```

### GalleryDetail (для детального просмотра)
```json
{
  "id": 1,
  "title": "Название галереи",
  "author_id": 123,
  "created_at": "2023-12-01T10:00:00Z",
  "updated_at": "2023-12-01T10:00:00Z",
  "views_count": 150,
  "likes_count": 25,
  "dislikes_count": 2,
  "comments_count": 8,
  "images": [
    {
      "id": 1,
      "image_url": "https://example.com/image1.jpg",
      "thumbnail_url": "https://example.com/thumb1.jpg",
      "dimensions": "1920x1080",
      "size": 1024000,
      "order_index": 0,
      "created_at": "2023-12-01T10:00:00Z"
    }
  ],
  "author": { /* UserInfo */ }
}
```

## Переменные окружения
- `DATABASE_URL`: URL подключения к PostgreSQL
- `AUTH_SERVICE_URL`: URL сервиса аутентификации
- `USER_SERVICE_URL`: URL сервиса пользователей
- `FILE_SERVICE_URL`: URL файлового сервиса

## Запуск
```bash
# Через Docker Compose
docker-compose up gallery_service

# Локально
cd backend/services/gallery_service
pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8010
```

## Особенности
- Автоматическое создание таблиц БД при запуске
- Поддержка пагинации для всех списков
- Автоматические счетчики для статистики
- Интеграция с другими сервисами через HTTP API
- Загрузка изображений через файловый сервис
- JWT аутентификация через auth_service 