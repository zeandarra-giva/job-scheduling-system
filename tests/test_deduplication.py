"""Deduplication service tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from api.services.deduplication import DeduplicationService
from api.schemas.requests import ArticleInput
from database.repositories.article_repo import ArticleStatus


class TestDeduplicationService:
    """Tests for DeduplicationService class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock()

    @pytest.fixture
    def dedup_service(self, mock_db):
        """Create deduplication service with mock db."""
        return DeduplicationService(mock_db)

    @pytest.mark.asyncio
    async def test_process_articles_all_new(self, dedup_service):
        """Test processing articles when all are new."""
        articles = [
            ArticleInput(
                url="https://example.com/article1",
                source="Test",
                category="Tech",
                priority=1
            )
        ]

        # Mock repository to return no existing articles
        dedup_service.article_repo.get_articles_by_urls = AsyncMock(return_value={})
        dedup_service.article_repo.create_article = AsyncMock(return_value={
            "_id": "art_001",
            "url": "https://example.com/article1",
            "status": ArticleStatus.PENDING
        })

        new_articles, cached_articles, cached_ids = await dedup_service.process_articles(articles)

        assert len(new_articles) == 1
        assert len(cached_articles) == 0
        assert len(cached_ids) == 0

    @pytest.mark.asyncio
    async def test_process_articles_all_cached(self, dedup_service):
        """Test processing articles when all are cached."""
        articles = [
            ArticleInput(
                url="https://example.com/article1",
                source="Test",
                category="Tech",
                priority=1
            )
        ]

        # Mock repository to return existing scraped article
        existing_article = {
            "_id": "art_001",
            "url": "https://example.com/article1",
            "status": ArticleStatus.SCRAPED
        }
        dedup_service.article_repo.get_articles_by_urls = AsyncMock(
            return_value={"https://example.com/article1": existing_article}
        )
        dedup_service.article_repo.increment_reference_count = AsyncMock(return_value=True)

        new_articles, cached_articles, cached_ids = await dedup_service.process_articles(articles)

        assert len(new_articles) == 0
        assert len(cached_articles) == 1
        assert "art_001" in cached_ids

    @pytest.mark.asyncio
    async def test_process_articles_mixed(self, dedup_service):
        """Test processing mix of new and cached articles."""
        articles = [
            ArticleInput(
                url="https://example.com/cached",
                source="Test",
                category="Tech",
                priority=1
            ),
            ArticleInput(
                url="https://example.com/new",
                source="Test",
                category="Tech",
                priority=2
            )
        ]

        # Mock existing cached article
        existing = {
            "_id": "art_cached",
            "url": "https://example.com/cached",
            "status": ArticleStatus.SCRAPED
        }
        dedup_service.article_repo.get_articles_by_urls = AsyncMock(
            return_value={"https://example.com/cached": existing}
        )
        dedup_service.article_repo.increment_reference_count = AsyncMock(return_value=True)
        dedup_service.article_repo.create_article = AsyncMock(return_value={
            "_id": "art_new",
            "url": "https://example.com/new",
            "status": ArticleStatus.PENDING
        })

        new_articles, cached_articles, cached_ids = await dedup_service.process_articles(articles)

        assert len(new_articles) == 1
        assert len(cached_articles) == 1
        assert new_articles[0]["url"] == "https://example.com/new"

    @pytest.mark.asyncio
    async def test_check_url_exists(self, dedup_service):
        """Test URL existence check."""
        dedup_service.article_repo.article_exists = AsyncMock(return_value=True)

        exists = await dedup_service.check_url_exists("https://example.com/test")
        assert exists

    @pytest.mark.asyncio
    async def test_check_url_scraped(self, dedup_service):
        """Test URL scraped status check."""
        dedup_service.article_repo.is_article_scraped = AsyncMock(return_value=True)

        scraped = await dedup_service.check_url_scraped("https://example.com/test")
        assert scraped
