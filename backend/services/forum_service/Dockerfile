FROM python:3.11-slim

WORKDIR /app

# Устанавливаем необходимые зависимости для Pillow
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем весь код приложения сначала
COPY ./src ./src
COPY ./config ./config
COPY ./database ./database
COPY pyproject.toml .
COPY __init__.py .

# Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pillow && \
    pip install --no-cache-dir -e .

# Создаем директорию для временных файлов
RUN mkdir -p /tmp && chmod 777 /tmp

# Переменные окружения для настройки приложения
ENV FORCE_DB_RECREATE=false

# Открываем порт
EXPOSE 8009

# Запускаем приложение
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8009"] 