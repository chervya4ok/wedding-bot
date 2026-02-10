from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .models import Base

# URL базы данных (локальный файл SQLite)
DATABASE_URL = "sqlite+aiosqlite:///./wedding_bot.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Создание таблиц при запуске"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)