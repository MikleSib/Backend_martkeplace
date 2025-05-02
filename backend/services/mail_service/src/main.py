from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import email
from email.header import decode_header
import email.utils
from datetime import datetime
import random
import os


app = FastAPI(
    title="Mail Service",
    description="Service for sending and receiving emails",
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS").lower() == "true"
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME")
EMAIL_DOMAIN = os.environ.get("EMAIL_DOMAIN")
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_ADDRESS_ENCODED = os.environ.get("EMAIL_ADDRESS_ENCODED")

class EmailRequest(BaseModel):
    to_email: EmailStr

class VerificationEmailRequest(BaseModel):
    to_email: EmailStr
    code: str

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/test")
async def test_email(email_request: EmailRequest):
    """
    Простой тестовый эндпоинт для отправки письма со словом "тест"
    """
    try:
        message = MIMEMultipart()
        
        from_name_encoded = email.header.Header(SMTP_FROM_NAME, 'utf-8').encode()
        message["From"] = f"{from_name_encoded} <{EMAIL_ADDRESS_ENCODED}>"
        message["To"] = email_request.to_email
        message["Subject"] = "тест"
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain=EMAIL_DOMAIN)
        message["MIME-Version"] = "1.0"
        
        text_content = "тест"
        html_content = "<p>тест</p>"
        
        text_part = MIMEText(text_content, "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        
        message.attach(text_part)
        message.attach(html_part)
        
        logger.info(f"Sending test email to {email_request.to_email}")
        
        smtp = aiosmtplib.SMTP(
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            use_tls=SMTP_USE_TLS,
            validate_certs=False
        )
        
        await smtp.connect()
        await smtp.login(EMAIL_ADDRESS_ENCODED, SMTP_PASSWORD)
        await smtp.send_message(message)
        await smtp.quit()

        logger.info(f"Test email sent successfully to {email_request.to_email}")
        return {"status": "success", "message": "Тестовое письмо отправлено"}

    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {str(e)}")

@app.post("/send-verification")
async def send_verification_code(email_request: VerificationEmailRequest):
    """
    Отправляет код подтверждения на почту при регистрации
    """
    try:
        message = MIMEMultipart()
        
        from_name_encoded = email.header.Header(SMTP_FROM_NAME, 'utf-8').encode()
        message["From"] = f"{from_name_encoded} <{EMAIL_ADDRESS_ENCODED}>"
        message["To"] = email_request.to_email
        message["Subject"] = "Код подтверждения регистрации"
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain=EMAIL_DOMAIN)
        message["MIME-Version"] = "1.0"
        
        # Создаем текст письма с кодом
        text_content = f"""
Добро пожаловать на Рыбный Форум!

Ваш код подтверждения регистрации: {email_request.code}

Код действителен в течение 15 минут. Если вы не запрашивали этот код, просто проигнорируйте это письмо.

С уважением,
Команда Рыбного Форума
        """
        
        html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <title>Код подтверждения регистрации</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 5px;">
        <h2 style="color: #0066cc;">Добро пожаловать на Рыбный Форум!</h2>
        <p>Для завершения регистрации, пожалуйста, введите следующий код:</p>
        <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 24px; letter-spacing: 5px; font-weight: bold; margin: 20px 0; border-radius: 4px;">
            {email_request.code}
        </div>
        <p>Код действителен в течение <strong>15 минут</strong>.</p>
        <p>Если вы не запрашивали этот код, просто проигнорируйте это письмо.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 14px; color: #777;">С уважением,<br>Команда Рыбного Форума</p>
    </div>
</body>
</html>
        """
        
        text_part = MIMEText(text_content, "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        
        message.attach(text_part)
        message.attach(html_part)
        
        logger.info(f"Sending verification code to {email_request.to_email}")
        
        smtp = aiosmtplib.SMTP(
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            use_tls=SMTP_USE_TLS,
            validate_certs=False
        )
        
        await smtp.connect()
        await smtp.login(EMAIL_ADDRESS_ENCODED, SMTP_PASSWORD)
        await smtp.send_message(message)
        await smtp.quit()

        logger.info(f"Verification code sent successfully to {email_request.to_email}")
        return {"status": "success", "message": "Код подтверждения отправлен"}

    except Exception as e:
        logger.error(f"Error sending verification code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send verification code: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)