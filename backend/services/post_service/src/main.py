from fastapi import FastAPI
from .endpoints import router
from database import engine
from database import Base
from database import create_tables

app = FastAPI()
app.include_router(router)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await create_tables()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

