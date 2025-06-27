import httpx
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

async def send_user_registration_notification(username: str, user_id: int, email: str) -> bool:
    """Отправляет уведомление о регистрации нового пользователя"""
    forum_url = "https://рыболовный-форум.рф"  # Базовый URL форума
    
    message = f"""
🎉 *НОВАЯ РЕГИСТРАЦИЯ* 🎉

*Пользователь:* {username} (ID: {user_id})
*Email:* {email}
*Дата:* {datetime.now().strftime("%d.%m.%Y %H:%M")}

*Профиль пользователя:* {forum_url}/forum/user/{user_id}
"""
    return await send_telegram_notification(message) 