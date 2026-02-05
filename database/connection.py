"""Database connection setup for MongoDB and Redis."""
import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import redis.asyncio as redis
from shared.config import settings


class DatabaseConnection:
    """Manages MongoDB and Redis connections."""

    _mongo_client: Optional[AsyncIOMotorClient] = None
    _redis_client: Optional[redis.Redis] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def init_mongo(cls) -> AsyncIOMotorDatabase:
        """Initialize MongoDB connection."""
        if cls._mongo_client is None:
            cls._mongo_client = AsyncIOMotorClient(settings.mongo_url)
            cls._db = cls._mongo_client[settings.mongo_db_name]
            await cls._setup_indexes()
        return cls._db

    @classmethod
    async def _setup_indexes(cls):
        """Set up MongoDB indexes for optimal query performance."""
        if cls._db is None:
            return

        # Articles collection indexes
        await cls._db.articles.create_index("url", unique=True)
        await cls._db.articles.create_index("status")
        await cls._db.articles.create_index("scraped_at")

        # Jobs collection indexes
        await cls._db.jobs.create_index("status")
        await cls._db.jobs.create_index("created_at")

    @classmethod
    async def get_mongo_db(cls) -> AsyncIOMotorDatabase:
        """Get MongoDB database instance."""
        if cls._db is None:
            await cls.init_mongo()
        return cls._db

    @classmethod
    async def init_redis(cls) -> redis.Redis:
        """Initialize Redis connection."""
        if cls._redis_client is None:
            cls._redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
        return cls._redis_client

    @classmethod
    async def get_redis(cls) -> redis.Redis:
        """Get Redis client instance."""
        if cls._redis_client is None:
            await cls.init_redis()
        return cls._redis_client

    @classmethod
    async def close_connections(cls):
        """Close all database connections."""
        if cls._mongo_client:
            cls._mongo_client.close()
            cls._mongo_client = None
            cls._db = None
        if cls._redis_client:
            await cls._redis_client.close()
            cls._redis_client = None


# Convenience functions
async def get_db() -> AsyncIOMotorDatabase:
    """Dependency for getting MongoDB database."""
    return await DatabaseConnection.get_mongo_db()


async def get_redis() -> redis.Redis:
    """Dependency for getting Redis client."""
    return await DatabaseConnection.get_redis()
