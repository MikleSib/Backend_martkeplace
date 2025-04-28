FROM python:3.12-slim as builder
WORKDIR /app/redis_service

COPY pyproject.toml ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

FROM python:3.12-slim as runtime
WORKDIR /app/redis_service

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"] 