# Документация API форума для фронтенд-разработчиков

## Общая информация

- **Базовый URL**: `http://localhost:8000`
- **Аутентификация**: Используется Bearer Token. Для большинства запросов требуется передача токена в заголовке `Authorization: Bearer <token>`
- **Формат данных**: JSON
- **Пагинация**: Для списков используется пагинация с параметрами `page` и `page_size`


### 2.1. Получение списка категорий
- **Endpoint**: `GET /forum/categories`
- **Требует авторизации**: Нет
- **Ответ**: Список категорий верхнего уровня
```json
[
  {
    "id": 0,
    "title": "string",
    "description": "string",
    "icon": "string",
    "order": 0,
    "parent_id": null,
    "topics_count": 0,
    "messages_count": 0
  }
]
```

### 2.2. Получение категории с подкатегориями
- **Endpoint**: `GET /forum/categories/{category_id}`
- **Требует авторизации**: Нет
- **Ответ**: Информация о категории с подкатегориями
```json
{
  "id": 0,
  "title": "string",
  "description": "string",
  "icon": "string",
  "order": 0,
  "parent_id": null,
  "topics_count": 0,
  "messages_count": 0,
  "subcategories": [
    {
      "id": 0,
      "title": "string",
      "description": "string",
      "icon": "string",
      "order": 0,
      "parent_id": 0,
      "topics_count": 0,
      "messages_count": 0
    }
  ]
}
```

### 2.3. Создание категории (только для админов)
- **Endpoint**: `POST /forum/categories`
- **Требует авторизации**: Да (администратор)
- **Тело запроса**:
```json
{
  "title": "string",
  "description": "string",
  "icon": "string",
  "order": 0,
  "parent_id": null
}
```
- **Ответ**: Созданная категория

### 2.4. Обновление категории (только для админов)
- **Endpoint**: `PUT /forum/categories/{category_id}`
- **Требует авторизации**: Да (администратор)
- **Тело запроса**:
```json
{
  "title": "string",
  "description": "string",
  "icon": "string",
  "order": 0,
  "parent_id": null
}
```
- **Ответ**: Обновленная категория

### 2.5. Удаление категории (только для админов)
- **Endpoint**: `DELETE /forum/categories/{category_id}`
- **Требует авторизации**: Да (администратор)
- **Ответ**: Сообщение об успешном удалении

## 3. Темы форума

### 3.1. Получение списка тем
- **Endpoint**: `GET /forum/topics`
- **Требует авторизации**: Нет
- **Параметры запроса**:
  - `category_id` (опционально): ID категории для фильтрации
  - `author_id` (опционально): ID автора для фильтрации
  - `pinned` (опционально): фильтрация закрепленных тем (boolean)
  - `page` (по умолчанию 1): номер страницы
  - `page_size` (по умолчанию 20, макс. 100): размер страницы
- **Ответ**: Пагинированный список тем
```json
{
  "items": [
    {
      "id": 0,
      "title": "string",
      "category_id": 0,
      "tags": ["string"],
      "author_id": 0,
      "created_at": "datetime",
      "is_closed": false,
      "is_pinned": false,
      "views_count": 0,
      "posts_count": 0,
      "last_post_id": null,
      "last_post_author_id": null,
      "last_post_date": null
    }
  ],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "pages": 0
}
```

### 3.2. Получение детальной информации о теме
- **Endpoint**: `GET /forum/topics/{topic_id}`
- **Требует авторизации**: Нет
- **Ответ**: Детальная информация о теме
```json
{
  "id": 0,
  "title": "string",
  "category_id": 0,
  "tags": ["string"],
  "author_id": 0,
  "created_at": "datetime",
  "is_closed": false,
  "is_pinned": false,
  "views_count": 0,
  "posts_count": 0,
  "last_post_id": null,
  "last_post_author_id": null,
  "last_post_date": null,
  "author_username": "string",
  "author_avatar": "string",
  "category_title": "string"
}
```

### 3.3. Создание новой темы
- **Endpoint**: `POST /forum/topics`
- **Требует авторизации**: Да
- **Тело запроса**:
```json
{
  "title": "string",
  "category_id": 0,
  "tags": ["string"],
  "content": "string"
}
```
- **Ответ**: Созданная тема

### 3.4. Обновление темы
- **Endpoint**: `PUT /forum/topics/{topic_id}`
- **Требует авторизации**: Да (владелец темы или модератор)
- **Тело запроса**:
```json
{
  "title": "string",
  "category_id": 0,
  "tags": ["string"],
  "is_closed": false,
  "is_pinned": false
}
```
- **Ответ**: Обновленная тема

### 3.5. Удаление темы
- **Endpoint**: `DELETE /forum/topics/{topic_id}`
- **Требует авторизации**: Да (владелец темы или модератор)
- **Ответ**: Сообщение об успешном удалении

### 3.6. Закрепление/открепление темы
- **Endpoint**: `PUT /forum/topics/{topic_id}/pin`
- **Требует авторизации**: Да (модератор)
- **Ответ**: Обновленная тема

### 3.7. Закрытие/открытие темы
- **Endpoint**: `PUT /forum/topics/{topic_id}/close`
- **Требует авторизации**: Да (модератор)
- **Ответ**: Обновленная тема

## 4. Сообщения форума

### 4.1. Получение списка сообщений в теме
- **Endpoint**: `GET /forum/posts`
- **Требует авторизации**: Нет
- **Параметры запроса**:
  - `topic_id`: ID темы (обязательный)
  - `page` (по умолчанию 1): номер страницы
  - `page_size` (по умолчанию 20, макс. 100): размер страницы
- **Ответ**: Пагинированный список сообщений
```json
{
  "items": [
    {
      "id": 0,
      "topic_id": 0,
      "author_id": 0,
      "content": "string",
      "quoted_post_id": null,
      "created_at": "datetime",
      "updated_at": "datetime",
      "is_topic_starter": false,
      "is_edited": false,
      "likes_count": 0,
      "dislikes_count": 0
    }
  ],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "pages": 0
}
```

### 4.2. Получение детальной информации о сообщении
- **Endpoint**: `GET /forum/posts/{post_id}`
- **Требует авторизации**: Нет
- **Ответ**: Детальная информация о сообщении
```json
{
  "id": 0,
  "topic_id": 0,
  "author_id": 0,
  "content": "string",
  "quoted_post_id": null,
  "created_at": "datetime",
  "updated_at": "datetime",
  "is_topic_starter": false,
  "is_edited": false,
  "likes_count": 0,
  "dislikes_count": 0,
  "author_username": "string",
  "author_avatar": "string",
  "author_signature": "string",
  "author_post_count": 0,
  "images": [
    {
      "id": 0,
      "image_url": "string",
      "thumbnail_url": "string",
      "dimensions": "string"
    }
  ],
  "quoted_content": "string",
  "quoted_author": "string"
}
```

### 4.3. Создание нового сообщения
- **Endpoint**: `POST /forum/posts`
- **Требует авторизации**: Да
- **Тело запроса**:
```json
{
  "topic_id": 0,
  "content": "string",
  "quoted_post_id": null
}
```
- **Ответ**: Созданное сообщение

### 4.4. Обновление сообщения
- **Endpoint**: `PUT /forum/posts/{post_id}`
- **Требует авторизации**: Да (владелец сообщения или модератор)
- **Тело запроса**:
```json
{
  "content": "string"
}
```
- **Ответ**: Обновленное сообщение

### 4.5. Удаление сообщения
- **Endpoint**: `DELETE /forum/posts/{post_id}`
- **Требует авторизации**: Да (владелец сообщения или модератор)
- **Ответ**: Сообщение об успешном удалении

### 4.6. Лайк сообщения
- **Endpoint**: `POST /forum/posts/{post_id}/like`
- **Требует авторизации**: Да
- **Ответ**: Информация о реакции

### 4.7. Дизлайк сообщения
- **Endpoint**: `POST /forum/posts/{post_id}/dislike`
- **Требует авторизации**: Да
- **Ответ**: Информация о реакции

### 4.8. Удаление реакции на сообщение
- **Endpoint**: `DELETE /forum/posts/{post_id}/reactions`
- **Требует авторизации**: Да
- **Ответ**: Информация о реакции

## 5. Ограничения и правила

1. **Темы**:
   - Минимальная длина заголовка: 5 символов
   - Максимальная длина заголовка: 255 символов
   - Максимальное количество тегов: 5
   - Максимальная длина тега: 20 символов

2. **Сообщения**:
   - Минимальная длина содержания темы: 10 символов
   - Минимальная длина сообщения: 1 символ

3. **Категории**:
   - Минимальная длина названия: 3 символа
   - Максимальная длина названия: 100 символов

4. **Загрузка изображений**:
   - Максимальный размер изображения: 8 МБ
   - Максимальное количество изображений на сообщение: 5
   - Разрешенные форматы: jpg, jpeg, png, gif

## 6. Статусы ошибок

- `400` - Неверный запрос (детали в сообщении об ошибке)
- `401` - Не авторизован
- `403` - Запрещено (недостаточно прав)
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера
- `503` - Сервис недоступен

## 7. Примеры использования

### Получение списка категорий
```javascript
async function getCategories() {
  const response = await fetch('http://localhost:8000/forum/categories');
  return await response.json();
}
```

### Создание новой темы
```javascript
async function createTopic(token, title, categoryId, content, tags = []) {
  const response = await fetch('http://localhost:8000/forum/topics', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      title,
      category_id: categoryId,
      content,
      tags
    })
  });
  return await response.json();
}
```

### Получение сообщений в теме
```javascript
async function getTopicPosts(topicId, page = 1, pageSize = 20) {
  const response = await fetch(`http://localhost:8000/forum/posts?topic_id=${topicId}&page=${page}&page_size=${pageSize}`);
  return await response.json();
}
```

### Добавление лайка сообщению
```javascript
async function likePost(token, postId) {
  const response = await fetch(`http://localhost:8000/forum/posts/${postId}/like`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return await response.json();
}
```

## 8. Рекомендации для фронтенд-разработчиков

1. Всегда сохраняйте токены доступа в безопасном месте (localStorage или cookies с флагом httpOnly)
2. Реализуйте автоматическое обновление токена при его истечении
3. Для оптимизации производительности используйте кэширование данных категорий и популярных тем
4. Для пагинации используйте компонент с возможностью навигации по страницам
5. При отображении контента учитывайте возможность использования разметки для форматирования текста
6. При создании форм используйте валидацию в соответствии с ограничениями API 