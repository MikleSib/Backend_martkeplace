from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import logging
import requests
from pydantic_settings import BaseSettings


load_dotenv()

class Settings(BaseSettings):
    smtp_host: str = os.getenv("SMTP_HOST", "mail.your-domain.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "no-reply@your-domain.com")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    smtp_use_ssl: bool = os.getenv("SMTP_USE_SSL", "False").lower() == "true"
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "Your Company Name")
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8001")

settings = Settings()

app = FastAPI(
    title="Mail Service",
    description="Service for sending emails",
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


security = HTTPBearer()

class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    template_name: Optional[str] = None
    template_data: Optional[dict] = None
    from_name: Optional[str] = None

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        response = requests.get(
            f"{settings.auth_service_url}/auth/check_token",
            params={"token": credentials.credentials}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        return response.json()
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/send")
async def send_email(
    email_request: EmailRequest,
    user_info: dict = Depends(verify_token)
):
    try:
        
        message = MIMEMultipart()
        from_name = email_request.from_name or settings.smtp_from_name
        message["From"] = f"{from_name} <{settings.smtp_user}>"
        message["To"] = email_request.to_email
        message["Subject"] = email_request.subject

        
        message.attach(MIMEText(email_request.body, "html"))

        
        smtp_kwargs = {
            "hostname": settings.smtp_host,
            "port": settings.smtp_port,
            "use_tls": settings.smtp_use_tls,
            "use_ssl": settings.smtp_use_ssl
        }

        
        async with aiosmtplib.SMTP(**smtp_kwargs) as smtp:
            if settings.smtp_use_tls:
                await smtp.starttls()
            await smtp.login(settings.smtp_user, settings.smtp_password)
            await smtp.send_message(message)

        logger.info(f"Email sent successfully to {email_request.to_email}")
        return {"message": "Email sent successfully"}

    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008) 