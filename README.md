Проект состоит из следующих микросервисов:

- **API Gateway** (порт 8000) - Самописный api geteway
- **Auth Service** (порт 8001) - Аутентификация и авторизация
- **User Service** (порт 8002) - Управление профилями пользователей
- **Redis Service** (порт 8003) - Кэширование данных
- **Post Service** (порт 8004) - Управление постами
- **File Service** (порт 8005) - Управление файлами и загрузками
- **News Service** (порт 8006) - Управление новостями и объявлениями
- **Admin Service** (порт 8007) - Административный интерфейс
- **Mail Service** (порт 8008) - Отправка email уведомлений

### Базы данных

- **db_auth** - база данных для сервиса аутентификации
- **db_user** - база данных для сервиса пользователей
- **db_post** - база данных для сервиса постов
- **db_news** - база данных для сервиса новостей
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

### File Service

- `POST /files/upload` - загрузка файла
- `GET /files/{file_id}` - получение файла
- `DELETE /files/{file_id}` - удаление файла

### News Service

- `POST /news/` - создание новости
- `GET /news/{news_id}` - получение новости по ID
- `GET /news/` - получение всех новостей
- `PATCH /news/{news_id}` - обновление новости
- `DELETE /news/{news_id}` - удаление новости

### Admin Service

- `GET /admin/stats` - получение статистики
- `GET /admin/users` - управление пользователями
- `GET /admin/posts` - управление постами
- `GET /admin/news` - управление новостями

### Mail Service

- `POST /mail/send` - отправка email
- `POST /mail/template` - отправка email по шаблону

## 🔐 Аутентификация

Все защищенные эндпоинты требуют JWT токен в заголовке:
```
Authorization: Bearer <token>
```
## 🔮 Планы на будущее

- Настройка CI/CD для автоматической сборки и деплоя
- Миграция на Kubernetes (в отдаленной перспективе, если время будет свободное)
- Добавить Kafka после создания сервисов Постов, Товаров
