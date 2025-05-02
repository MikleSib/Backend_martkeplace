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

# Настройки почты
EMAIL = "support@рыбный-форум.рф"
EMAIL_ENCODED = "support@xn----9sbyncijf1ah6ec.xn--p1ai"
PASSWORD = "cOu!Z{<8g@DBB7"
DOMAIN = "xn----9sbyncijf1ah6ec.xn--p1ai"

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
        from_name = "Рыбный Форум"
        
        from_name_encoded = email.header.Header(from_name, 'utf-8').encode()
        message["From"] = f"{from_name_encoded} <{EMAIL_ENCODED}>"
        message["To"] = email_request.to_email
        message["Subject"] = "тест"
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain=DOMAIN)
        message["MIME-Version"] = "1.0"
        
        text_content = "тест"
        html_content = "<p>тест</p>"
        
        text_part = MIMEText(text_content, "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        
        message.attach(text_part)
        message.attach(html_part)
        
        logger.info(f"Sending test email to {email_request.to_email}")
        
        smtp = aiosmtplib.SMTP(
            hostname="smtp.timeweb.ru",
            port=465,
            use_tls=True,
            validate_certs=False
        )
        
        await smtp.connect()
        await smtp.login(EMAIL_ENCODED, PASSWORD)
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
        from_name = "Рыбный Форум"
        
        from_name_encoded = email.header.Header(from_name, 'utf-8').encode()
        message["From"] = f"{from_name_encoded} <{EMAIL_ENCODED}>"
        message["To"] = email_request.to_email
        message["Subject"] = "Код подтверждения регистрации"
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain=DOMAIN)
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
            hostname="smtp.timeweb.ru",
            port=465,
            use_tls=True,
            validate_certs=False
        )
        
        await smtp.connect()
        await smtp.login(EMAIL_ENCODED, PASSWORD)
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