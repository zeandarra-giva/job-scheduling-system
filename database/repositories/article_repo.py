"""Article repository for CRUD operations on Articles collection."""
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from shared.utils import generate_article_id, get_utc_now, normalize_url


class ArticleStatus:
    """Article status constants."""
    PENDING = "PENDING"
    SCRAPING = "SCRAPING"
    SCRAPED = "SCRAPED"
    FAILED = "FAILED"


class ArticleRepository:
    """Repository for Article CRUD operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.articles

    async def create_article(
        self,
        url: str,
        source: str,
        category: str,
        priority: int = 1
    ) -> Dict[str, Any]:
        """Create a new article record."""
        article_id = generate_article_id()
        now = get_utc_now()
        normalized_url = normalize_url(url)

        article = {
            "_id": article_id,
            "url": normalized_url,
            "source": source,
            "category": category,
            "priority": priority,
            "title": None,
            "content": None,
            "status": ArticleStatus.PENDING,
            "error_message": None,
            "scraped_at": None,
            "created_at": now,
            "updated_at": now,
            "reference_count": 1,
            "retry_count": 0
        }

        try:
            await self.collection.insert_one(article)
            return article
        except Exception as e:
            # Handle duplicate key error
            if "duplicate key" in str(e).lower():
                return await self.get_article_by_url(normalized_url)
            raise

    async def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get an article by ID."""
        return await self.collection.find_one({"_id": article_id})

    async def get_article_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get an article by URL."""
        normalized_url = normalize_url(url)
        return await self.collection.find_one({"url": normalized_url})

    async def get_articles_by_urls(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple articles by their URLs. Returns dict mapping URL to article."""
        normalized_urls = [normalize_url(url) for url in urls]
        cursor = self.collection.find({"url": {"$in": normalized_urls}})
        articles = await cursor.to_list(length=len(urls))
        return {article["url"]: article for article in articles}

    async def get_articles_by_ids(self, article_ids: List[str]) -> List[Dict[str, Any]]:
        """Get multiple articles by their IDs."""
        cursor = self.collection.find({"_id": {"$in": article_ids}})
        return await cursor.to_list(length=len(article_ids))

    async def update_article_status(
        self,
        article_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update article status."""
        update = {
            "$set": {
                "status": status,
                "updated_at": get_utc_now()
            }
        }
        if error_message is not None:
            update["$set"]["error_message"] = error_message

        result = await self.collection.update_one(
            {"_id": article_id},
            update
        )
        return result.modified_count > 0

    async def update_article_content(
        self,
        article_id: str,
        title: str,
        content: str
    ) -> bool:
        """Update article with scraped content."""
        now = get_utc_now()
        result = await self.collection.update_one(
            {"_id": article_id},
            {
                "$set": {
                    "title": title,
                    "content": content,
                    "status": ArticleStatus.SCRAPED,
                    "scraped_at": now,
                    "updated_at": now,
                    "error_message": None
                }
            }
        )
        return result.modified_count > 0

    async def mark_article_failed(
        self,
        article_id: str,
        error_message: str
    ) -> bool:
        """Mark article as failed with error message."""
        result = await self.collection.update_one(
            {"_id": article_id},
            {
                "$set": {
                    "status": ArticleStatus.FAILED,
                    "error_message": error_message,
                    "updated_at": get_utc_now()
                }
            }
        )
        return result.modified_count > 0

    async def increment_reference_count(self, article_id: str) -> bool:
        """Increment the reference count for an article."""
        result = await self.collection.update_one(
            {"_id": article_id},
            {
                "$inc": {"reference_count": 1},
                "$set": {"updated_at": get_utc_now()}
            }
        )
        return result.modified_count > 0

    async def increment_retry_count(self, article_id: str) -> Optional[int]:
        """Increment retry count and return new count."""
        result = await self.collection.find_one_and_update(
            {"_id": article_id},
            {
                "$inc": {"retry_count": 1},
                "$set": {"updated_at": get_utc_now()}
            },
            return_document=True
        )
        return result["retry_count"] if result else None

    async def reset_article_for_retry(self, article_id: str) -> bool:
        """Reset article status for retry."""
        result = await self.collection.update_one(
            {"_id": article_id},
            {
                "$set": {
                    "status": ArticleStatus.PENDING,
                    "error_message": None,
                    "updated_at": get_utc_now()
                }
            }
        )
        return result.modified_count > 0

    async def article_exists(self, url: str) -> bool:
        """Check if an article with the given URL exists."""
        normalized_url = normalize_url(url)
        count = await self.collection.count_documents({"url": normalized_url})
        return count > 0

    async def is_article_scraped(self, url: str) -> bool:
        """Check if an article has been successfully scraped."""
        normalized_url = normalize_url(url)
        article = await self.collection.find_one({
            "url": normalized_url,
            "status": ArticleStatus.SCRAPED
        })
        return article is not None

    async def get_or_create_article(
        self,
        url: str,
        source: str,
        category: str,
        priority: int = 1
    ) -> tuple[Dict[str, Any], bool]:
        """Get existing article or create new one. Returns (article, is_new)."""
        existing = await self.get_article_by_url(url)
        if existing:
            # Increment reference count for existing article
            await self.increment_reference_count(existing["_id"])
            return existing, False

        # Create new article
        article = await self.create_article(url, source, category, priority)
        return article, True
