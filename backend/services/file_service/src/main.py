from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from datetime import datetime
import uuid
from typing import List, Optional
import logging
from fastapi.responses import FileResponse
import base64
from PIL import Image
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def optimize_image(image_data: bytes, max_dimension: int = 1920, quality: int = 52) -> bytes:
    """Оптимизирует изображение: сохраняет пропорции, ограничивает максимальную сторону и конвертирует в WebP"""
    try:
        # Открываем изображение из байтов
        img = Image.open(io.BytesIO(image_data))
        
        # Конвертируем в RGB если нужно
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Получаем текущие размеры
        width, height = img.size
        
        # Вычисляем новые размеры, сохраняя пропорции
        if width > height:
            if width > max_dimension:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_width, new_height = width, height
        else:
            if height > max_dimension:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))
            else:
                new_width, new_height = width, height
        
        # Изменяем размер с сохранением пропорций
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Сохраняем в WebP формате
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error optimizing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error optimizing image: {str(e)}")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Проверяем, является ли файл изображением
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Читаем содержимое файла
        file_content = await file.read()
        
        # Оптимизируем изображение
        optimized_image = optimize_image(file_content)
        
        # Генерируем уникальное имя файла с расширением .webp
        unique_filename = f"{uuid.uuid4()}.webp"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Сохраняем оптимизированное изображение
        with open(file_path, "wb") as buffer:
            buffer.write(optimized_image)
        
        file_url = f"/files/{unique_filename}"
        file_size = os.path.getsize(file_path)
        
        return {
            "filename": unique_filename,
            "original_filename": file.filename,
            "url": file_url,
            "size": file_size,
            "content_type": "image/webp"
        }
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@app.get("/files/{filename}")
async def get_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005) 