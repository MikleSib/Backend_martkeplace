FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем директорию для загрузок
RUN mkdir -p uploads

EXPOSE 8005

CMD ["python", "src/main.py"] 