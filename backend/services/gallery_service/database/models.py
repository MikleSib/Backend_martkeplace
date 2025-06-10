from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Gallery(Base):
    __tablename__ = "galleries"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    author_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    views_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    dislikes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    
    # Связи
    images = relationship("GalleryImage", back_populates="gallery", cascade="all, delete-orphan")
    comments = relationship("GalleryComment", back_populates="gallery", cascade="all, delete-orphan")
    reactions = relationship("GalleryReaction", back_populates="gallery", cascade="all, delete-orphan")

class GalleryImage(Base):
    __tablename__ = "gallery_images"
    
    id = Column(Integer, primary_key=True, index=True)
    gallery_id = Column(Integer, ForeignKey("galleries.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    dimensions = Column(String(50), nullable=True)  # например "1920x1080"
    size = Column(Integer, default=0)  # размер в байтах
    order_index = Column(Integer, default=0)  # порядок отображения
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    gallery = relationship("Gallery", back_populates="images")

class GalleryComment(Base):
    __tablename__ = "gallery_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    gallery_id = Column(Integer, ForeignKey("galleries.id"), nullable=False)
    author_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    
    # Связи
    gallery = relationship("Gallery", back_populates="comments")

class GalleryReaction(Base):
    __tablename__ = "gallery_reactions"
    
    id = Column(Integer, primary_key=True, index=True)
    gallery_id = Column(Integer, ForeignKey("galleries.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    type = Column(String(10), nullable=False)  # LIKE или DISLIKE
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    gallery = relationship("Gallery", back_populates="reactions")

class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("gallery_comments.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    type = Column(String(10), nullable=False)  # LIKE или DISLIKE
    created_at = Column(DateTime, default=datetime.utcnow) 