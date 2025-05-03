from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)  
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    about_me = Column(Text, nullable=True)
    avatar = Column(String, nullable=True)  # URL аватара пользователя
    signature = Column(String, nullable=True)  # Подпись, отображаемая под сообщениями
    registration_date = Column(DateTime, default=datetime.utcnow)  # Дата регистрации
    posts_count = Column(Integer, default=0)  # Количество сообщений
    role = Column(String, default="user")  # Роль пользователя: user, moderator, admin