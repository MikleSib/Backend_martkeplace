import httpx
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Telegram bot credentials
TELEGRAM_BOT_TOKEN = "7668995111:AAFwYME1gQX6kd5kfsEKg4l0kYQt_iFQI-U"
TELEGRAM_CHAT_ID = "-4744201336"

async def send_telegram_notification(message: str, parse_mode: str = "Markdown") -> bool:
    """
    Отправляет уведомление в Telegram
    
    Args:
        message: Текст сообщения
        parse_mode: Режим парсинга (Markdown или HTML)
    
    Returns:
        True если сообщение отправлено успешно, False если произошла ошибка
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": parse_mode
                }
            )
            telegram_result = response.json()
            
            if not telegram_result.get("ok", False):
                logger.error(f"Ошибка отправки в Telegram: {telegram_result}")
                return False
            
            logger.info("Уведомление в Telegram успешно отправлено")
            return True
            
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {str(e)}")
        return False

async def send_user_registration_notification(username: str, user_id: int, email: str, forum_url: str = "https://рыболовный-форум.рф") -> bool:
    """Отправляет уведомление о регистрации нового пользователя"""
    message = f"""
🎉 *НОВАЯ РЕГИСТРАЦИЯ* 🎉

*Пользователь:* {username} (ID: {user_id})
*Email:* {email}
*Дата:* {datetime.now().strftime("%d.%m.%Y %H:%M")}

*Профиль пользователя:* {forum_url}/forum/user/{user_id}
"""
    return await send_telegram_notification(message)

async def send_topic_creation_notification(
    topic_title: str, 
    topic_id: int, 
    category_title: str,
    author_username: str, 
    author_id: int,
    content_preview: str,
    forum_url: str = "https://рыболовный-форум.рф"
) -> bool:
    """Отправляет уведомление о создании новой темы"""
    short_content = (content_preview[:50] + ("..." if len(content_preview) > 50 else "")) if content_preview else ""
    message = f"""
📝 *НОВАЯ ТЕМА НА ФОРУМЕ* 📝

*Автор:* {author_username} (ID: {author_id})
*Заголовок:* {topic_title}
*Категория:* {category_title}
*ID темы:* {topic_id}

*Содержание:*
```
{short_content}
```

*Ссылка на тему:* {forum_url}/forum/topic/{topic_id}
"""
    return await send_telegram_notification(message)

async def send_post_creation_notification(
    post_id: int,
    topic_title: str,
    topic_id: int,
    author_username: str,
    author_id: int,
    content_preview: str,
    forum_url: str = "https://рыболовный-форум.рф",
    is_topic_starter: bool = False
) -> bool:
    """Отправляет уведомление о создании нового поста"""
    print(f"DEBUG: send_post_creation_notification вызвана для поста {post_id}, is_topic_starter={is_topic_starter}")
    
    if is_topic_starter:
        # Не отправляем уведомление для стартового поста, так как уже отправили для темы
        print(f"DEBUG: Пропускаем уведомление для стартового поста {post_id}")
        return True
        
    short_content = (content_preview[:50] + ("..." if len(content_preview) > 50 else "")) if content_preview else ""
    message = f"""
💬 *НОВЫЙ ПОСТ НА ФОРУМЕ* 💬

*Автор:* {author_username} (ID: {author_id})
*Тема:* {topic_title}
*ID поста:* {post_id}

*Содержание:*
```
{short_content}
```

*Ссылка на пост:* {forum_url}/forum/topic/{topic_id}?post={post_id}
"""
    print(f"DEBUG: Отправляем уведомление о посте {post_id}: {message[:100]}...")
    result = await send_telegram_notification(message)
    print(f"DEBUG: Результат отправки уведомления о посте {post_id}: {result}")
    return result

# Импортируем datetime для использования в функциях 