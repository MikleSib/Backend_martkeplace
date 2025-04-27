from fastapi import FastAPI
from .endpoints import router
from database import engine
from database import Base

app = FastAPI()
app.include_router(router)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health_check():
    return {"message": "health check"}

