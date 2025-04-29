Проект состоит из следующих микросервисов:

- **API Gateway** (порт 8000) - Самописный api geteway
- **Auth Service** (порт 8001) - Аутентификация и авторизация
- **User Service** (порт 8002) - Управление профилями пользователей
- **Redis Service** (порт 8003) - Кэширование данных
- **Post Service** (порт 8004) - Управление постами

### Базы данных

- **db_auth** - база данных для сервиса аутентификации
- **db_user** - база данных для сервиса пользователей
- **db_post** - база данных для сервиса постов
- **redis** - кэш-хранилище

## 🚀 Технологии

- FastAPI
- PostgreSQL
- SQLAlchemy
- Docker & Docker Compose
- JWT
- Redis

## 📋 Требования

- Docker
- Docker Compose
- Python 3.12+

## 🔧 Установка и запуск

1. Клонируйте репозиторий:
```bash
git clone https://github.com/MikleSib/Backend_martkeplace.git
```

2. Создайте файл `.env` в корневой директории

3. Запустите проект:
```bash
docker-compose up --build
```

## 📡 API Endpoints

### Auth Service

- `POST /auth/register` - регистрация нового пользователя
- `POST /auth/login` - вход в систему
- `POST /auth/refresh` - обновление токена
- `GET /auth/check_token` - проверка валидности токена

### User Service

- `POST /profile` - создание профиля пользователя
- `GET /profile/{user_id}` - получение профиля пользователя
- `PUT /profile/{user_id}` - обновление профиля

### Post Service

- `POST /posts/` - создание нового поста
- `GET /posts/{post_id}` - получение поста по ID
- `GET /posts/` - получение всех постов
- `GET /users/{author_id}/posts/` - получение постов пользователя
- `PATCH /posts/{post_id}` - обновление поста
- `DELETE /posts/{post_id}` - удаление поста

## 🔐 Аутентификация

Все защищенные эндпоинты требуют JWT токен в заголовке:
```
Authorization: Bearer <token>
```
## 🔮 Планы на будущее

- Настройка CI/CD для автоматической сборки и деплоя
- Миграция на Kubernetes (в отдаленной перспективе, если время будет свободное)
- Добавить Kafka после создания сервисов Постов, Товаров
