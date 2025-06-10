from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers import galleries, comments, reactions
from database.database import create_tables

app = FastAPI(
    title="Gallery Service",
    description="Сервис для управления фотогалереями",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(galleries.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")
app.include_router(reactions.router, prefix="/api/v1")

@app.on_event("startup")
async def startup():
    await create_tables()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010) 