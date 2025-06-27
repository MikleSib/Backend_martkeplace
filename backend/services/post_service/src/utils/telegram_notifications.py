import httpx
import logging

TELEGRAM_BOT_TOKEN = "7668995111:AAFwYME1gQX6kd5kfsEKg4l0kYQt_iFQI-U"
TELEGRAM_CHAT_ID = "-4744201336"

logger = logging.getLogger(__name__)

async def send_post_notification(post_id: int, title: str, content: str, author_id: int):
    short_content = (content[:50] + "...") if len(content) > 50 else content
    url = f"https://рыболовный-форум.рф/post/{post_id}"
    message = (
        f"💬 *НОВЫЙ ПОСТ НА ФОРУМЕ* 💬\n\n"
        f"*ID поста:* {post_id}\n"
        f"*Автор ID:* {author_id}\n"
        f"*Заголовок:* {title}\n"
        f"*Содержание:*\n```
{short_content}
```\n"
        f"*Ссылка на пост:* {url}"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )
            telegram_result = response.json()
            if not telegram_result.get("ok", False):
                logger.error(f"Ошибка отправки в Telegram: {telegram_result}")
                return False
            logger.info("Уведомление о посте успешно отправлено")
            return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {str(e)}")
        return False 