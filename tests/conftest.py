"""Pytest configuration and fixtures."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_mongo_db():
    """Create mock MongoDB database."""
    db = MagicMock()

    # Mock collections
    db.jobs = MagicMock()
    db.articles = MagicMock()

    # Mock common operations
    db.jobs.find_one = AsyncMock()
    db.jobs.insert_one = AsyncMock()
    db.jobs.update_one = AsyncMock()
    db.jobs.find = MagicMock()

    db.articles.find_one = AsyncMock()
    db.articles.insert_one = AsyncMock()
    db.articles.update_one = AsyncMock()
    db.articles.find = MagicMock()

    return db


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    redis = AsyncMock()

    redis.lpush = AsyncMock(return_value=1)
    redis.rpop = AsyncMock(return_value=None)
    redis.llen = AsyncMock(return_value=0)
    redis.publish = AsyncMock(return_value=1)
    redis.lrange = AsyncMock(return_value=[])
    redis.lrem = AsyncMock(return_value=1)

    return redis


@pytest.fixture
def sample_job():
    """Create sample job data."""
    return {
        "_id": "job_test123",
        "status": "IN_PROGRESS",
        "total_articles": 5,
        "new_articles": 3,
        "cached_articles": 2,
        "completed_count": 2,
        "failed_count": 0,
        "article_ids": ["art_001", "art_002"],
        "created_at": "2024-02-04T10:30:00Z",
        "updated_at": "2024-02-04T10:35:00Z",
        "completed_at": None
    }


@pytest.fixture
def sample_article():
    """Create sample article data."""
    return {
        "_id": "art_test001",
        "url": "https://example.com/test-article",
        "source": "TestSource",
        "category": "Technology",
        "priority": 1,
        "title": "Test Article Title",
        "content": "This is the test article content...",
        "status": "SCRAPED",
        "error_message": None,
        "scraped_at": "2024-02-04T10:32:00Z",
        "created_at": "2024-02-04T10:30:00Z",
        "updated_at": "2024-02-04T10:32:00Z",
        "reference_count": 1,
        "retry_count": 0
    }


@pytest.fixture
def sample_task():
    """Create sample scraping task."""
    return {
        "task_id": "task_test001",
        "job_id": "job_test123",
        "article_id": "art_test001",
        "url": "https://example.com/test-article",
        "source": "TestSource",
        "category": "Technology",
        "priority": 1,
        "retry_count": 0
    }
