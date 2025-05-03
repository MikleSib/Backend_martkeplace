from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (Boolean, Column, DateTime, Enum as SQLAlchemyEnum, 
                        ForeignKey, Integer, String, Text, ARRAY)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class ReactionType(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"

class NotificationType(str, Enum):
    REPLY = "reply"
    QUOTE = "quote"
    MENTION = "mention"
    LIKE = "like"

class ReferenceType(str, Enum):
    POST = "post"
    TOPIC = "topic"

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(255), nullable=True)
    order = Column(Integer, default=0)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    topics_count = Column(Integer, default=0)
    messages_count = Column(Integer, default=0)
    
    topics = relationship("Topic", back_populates="category")
    subcategories = relationship("Category", 
                              backref="parent",
                              remote_side=[id])
    
class Topic(Base):
    __tablename__ = "topics"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    author_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_closed = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    views_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    last_post_id = Column(Integer, nullable=True)
    last_post_author_id = Column(Integer, nullable=True)
    last_post_date = Column(DateTime, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    
    category = relationship("Category", back_populates="topics")
    posts = relationship("Post", back_populates="topic")
    bookmarks = relationship("Bookmark", back_populates="topic")
    
class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    author_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_topic_starter = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    likes_count = Column(Integer, default=0)
    dislikes_count = Column(Integer, default=0)
    quoted_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)
    
    topic = relationship("Topic", back_populates="posts")
    images = relationship("Image", back_populates="post")
    reactions = relationship("Reaction", back_populates="post")
    quoted_by = relationship("Post", 
                          backref="quoted_post",
                          remote_side=[id])
    
class Image(Base):
    __tablename__ = "images"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    author_id = Column(Integer, nullable=False)
    image_url = Column(String(255), nullable=False)
    thumbnail_url = Column(String(255), nullable=True)
    size = Column(Integer, nullable=False)  # в байтах
    dimensions = Column(String(20), nullable=True)  # например "1920x1080"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    post = relationship("Post", back_populates="images")
    
class Reaction(Base):
    __tablename__ = "reactions"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    type = Column(SQLAlchemyEnum(ReactionType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    post = relationship("Post", back_populates="reactions")
    
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    sender_id = Column(Integer, nullable=False)
    type = Column(SQLAlchemyEnum(NotificationType), nullable=False)
    content = Column(String(255), nullable=True)
    reference_id = Column(Integer, nullable=False)
    reference_type = Column(SQLAlchemyEnum(ReferenceType), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Bookmark(Base):
    __tablename__ = "bookmarks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    topic = relationship("Topic", back_populates="bookmarks")

class PostReport(Base):
    """Модель для хранения жалоб на сообщения"""
    __tablename__ = "post_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = Column(Integer, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    post = relationship("Post") 