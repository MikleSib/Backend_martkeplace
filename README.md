Проект состоит из следующих микросервисов:

- **API Gateway** (порт 8000) - Самописный api geteway
- **Auth Service** (порт 8001) - Аутентификация и авторизация
- **User Service** (порт 8002) - Управление профилями пользователей

### Базы данных

- **db_auth** - база данных для сервиса аутентификации
- **db_user** - база данных для сервиса пользователей

## 🚀 Технологии

- FastAPI
- PostgreSQL
- SQLAlchemy
- Docker & Docker Compose
- JWT 

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

### User Service

- `POST /profile` - создание профиля пользователя
- `GET /profile/{user_id}` - получение профиля пользователя
- `PUT /profile/{user_id}` - обновление профиля

## 🔐 Аутентификация

Все защищенные эндпоинты требуют JWT токен в заголовке:
```
Authorization: Bearer <token>
```
## 🔮 Планы на будущее

- Интеграция Redis 
- Настройка CI/CD для автоматической сборки и деплоя
- Миграция на Kubernetes (в отдаленной перспективе, если время будет свободное)
