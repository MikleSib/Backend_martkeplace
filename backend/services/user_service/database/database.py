import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
logger.info(f"Initializing database connection with URL: {DATABASE_URL}")

engine = create_async_engine(DATABASE_URL, echo=True)
logger.info("Database engine created successfully")

SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
logger.info("Session factory created successfully")

async def get_db():
    logger.debug("Creating new database session")
    async with SessionLocal() as session:
        try:
            yield session
            logger.debug("Database session completed successfully")
        except Exception as e:
            logger.error(f"Error in database session: {str(e)}")
            raise