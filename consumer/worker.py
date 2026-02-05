"""Worker process for consuming and processing scraping tasks."""
import asyncio
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.repositories.job_repo import JobRepository, JobStatus
from database.repositories.article_repo import ArticleRepository, ArticleStatus
from consumer.scraper import ArticleScraper
from shared.config import settings
from shared.utils import calculate_exponential_backoff

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScrapingWorker:
    """Worker that processes scraping tasks from Redis queue."""

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        redis_client: redis.Redis,
        worker_id: str = "worker-1"
    ):
        self.db = db
        self.redis = redis_client
        self.worker_id = worker_id
        self.job_repo = JobRepository(db)
        self.article_repo = ArticleRepository(db)
        self.scraper = ArticleScraper()
        self.running = True
        self.priority_queues = [
            f"{settings.redis_priority_queue_prefix}:high",
            f"{settings.redis_priority_queue_prefix}:medium",
            f"{settings.redis_priority_queue_prefix}:low"
        ]

    async def start(self):
        """Start the worker loop."""
        logger.info(f"Worker {self.worker_id} starting...")

        while self.running:
            task = await self._get_next_task()

            if task:
                await self._process_task(task)
            else:
                # No tasks available, wait before polling again
                await asyncio.sleep(settings.consumer_poll_interval)

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info(f"Worker {self.worker_id} stopping...")
        self.running = False

    async def _get_next_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the next task from Redis queues.
        Uses priority ordering: high > medium > low
        """
        for queue in self.priority_queues:
            result = await self.redis.rpop(queue)
            if result:
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse task: {result}")
                    continue
        return None

    async def _process_task(self, task: Dict[str, Any]):
        """Process a single scraping task."""
        article_id = task.get("article_id")
        job_id = task.get("job_id")
        url = task.get("url")
        retry_count = task.get("retry_count", 0)

        logger.info(f"Worker {self.worker_id} processing: {url}")

        # Check if job was cancelled
        job = await self.job_repo.get_job(job_id)
        if not job or job["status"] == JobStatus.CANCELLED:
            logger.info(f"Job {job_id} cancelled, skipping task")
            return

        # Update article status to SCRAPING
        await self.article_repo.update_article_status(article_id, ArticleStatus.SCRAPING)

        # Scrape the article
        result = await self.scraper.scrape(url)

        if result.success:
            await self._handle_success(article_id, job_id, result.title, result.content)
        else:
            await self._handle_failure(task, result.error, retry_count)

    async def _handle_success(
        self,
        article_id: str,
        job_id: str,
        title: str,
        content: str
    ):
        """Handle successful scraping."""
        # Update article with content
        await self.article_repo.update_article_content(article_id, title, content)

        # Increment job completed count
        job = await self.job_repo.increment_completed(job_id)

        # Check if job is complete
        if job:
            await self.job_repo.check_and_update_job_completion(job_id)

            # Publish update for WebSocket
            await self._publish_update(job_id, article_id, job)

        logger.info(f"Successfully scraped article {article_id}")

    async def _handle_failure(
        self,
        task: Dict[str, Any],
        error: str,
        retry_count: int
    ):
        """Handle failed scraping with retry logic."""
        article_id = task["article_id"]
        job_id = task["job_id"]

        if retry_count < settings.max_retry_attempts:
            # Schedule retry with exponential backoff
            delay = calculate_exponential_backoff(retry_count)
            logger.info(f"Retrying article {article_id} in {delay}s (attempt {retry_count + 1})")

            # Wait before re-queuing
            await asyncio.sleep(delay)

            # Increment retry count and re-queue
            task["retry_count"] = retry_count + 1
            queue = self.priority_queues[0]  # Use high priority for retries
            await self.redis.lpush(queue, json.dumps(task))

            # Reset article status to pending
            await self.article_repo.reset_article_for_retry(article_id)
        else:
            # Max retries exceeded, mark as failed
            await self.article_repo.mark_article_failed(article_id, error)

            # Increment job failed count
            job = await self.job_repo.increment_failed(job_id)

            # Check if job is complete
            if job:
                await self.job_repo.check_and_update_job_completion(job_id)
                await self._publish_update(job_id, article_id, job)

            logger.error(f"Article {article_id} failed after {retry_count + 1} attempts: {error}")

    async def _publish_update(
        self,
        job_id: str,
        article_id: str,
        job: Dict[str, Any]
    ):
        """Publish job update to Redis for WebSocket notification."""
        update = {
            "type": "job_update",
            "job_id": job_id,
            "article_id": article_id,
            "status": job["status"],
            "completed": job["completed_count"],
            "failed": job["failed_count"],
            "total": job["total_articles"]
        }
        await self.redis.publish(settings.redis_result_channel, json.dumps(update))
