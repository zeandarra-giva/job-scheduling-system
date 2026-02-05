"""Deduplication service for article management."""
from typing import List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from database.repositories.article_repo import ArticleRepository, ArticleStatus
from api.schemas.requests import ArticleInput
from shared.utils import normalize_url


class DeduplicationService:
    """Service for handling article deduplication logic."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.article_repo = ArticleRepository(db)

    async def process_articles(
        self,
        articles: List[ArticleInput]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """
        Process article list and separate into new vs cached articles.

        Returns:
            Tuple of (new_articles, cached_articles, cached_article_ids)
            - new_articles: List of article dicts that need to be scraped
            - cached_articles: List of existing article dicts from cache
            - cached_article_ids: List of article IDs that are cached
        """
        # Normalize all URLs for lookup
        urls = [normalize_url(article.url) for article in articles]

        # Batch lookup existing articles
        existing_articles = await self.article_repo.get_articles_by_urls(urls)

        new_articles = []
        cached_articles = []
        cached_article_ids = []

        for article in articles:
            normalized_url = normalize_url(article.url)
            existing = existing_articles.get(normalized_url)

            if existing and existing["status"] == ArticleStatus.SCRAPED:
                # Article already scraped - use from cache
                await self.article_repo.increment_reference_count(existing["_id"])
                cached_articles.append(existing)
                cached_article_ids.append(existing["_id"])
            else:
                # Need to create or re-scrape this article
                if existing:
                    # Existing but failed/pending - reset for retry
                    await self.article_repo.reset_article_for_retry(existing["_id"])
                    new_articles.append({
                        "article_id": existing["_id"],
                        "url": article.url,
                        "source": article.source,
                        "category": article.category,
                        "priority": article.priority,
                        "is_existing": True
                    })
                else:
                    # Create new article record
                    new_article = await self.article_repo.create_article(
                        url=article.url,
                        source=article.source,
                        category=article.category,
                        priority=article.priority
                    )
                    new_articles.append({
                        "article_id": new_article["_id"],
                        "url": article.url,
                        "source": article.source,
                        "category": article.category,
                        "priority": article.priority,
                        "is_existing": False
                    })

        return new_articles, cached_articles, cached_article_ids

    async def check_url_exists(self, url: str) -> bool:
        """Check if a URL already exists in the database."""
        return await self.article_repo.article_exists(url)

    async def check_url_scraped(self, url: str) -> bool:
        """Check if a URL has been successfully scraped."""
        return await self.article_repo.is_article_scraped(url)
