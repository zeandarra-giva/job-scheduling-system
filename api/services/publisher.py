"""Publisher service for pushing tasks to Redis queue."""
import json
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
from shared.config import settings
from shared.utils import generate_task_id


class PublisherService:
    """Service for publishing scraping tasks to Redis queue."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.queue_name = settings.redis_queue_name
        self.priority_prefix = settings.redis_priority_queue_prefix
        self.result_channel = settings.redis_result_channel

    def _get_priority_queue_name(self, priority: int) -> str:
        """Get queue name for a specific priority level."""
        # Lower number = higher priority
        # Priority 1-3: high, 4-7: medium, 8-10: low
        if priority <= 3:
            return f"{self.priority_prefix}:high"
        elif priority <= 7:
            return f"{self.priority_prefix}:medium"
        else:
            return f"{self.priority_prefix}:low"

    async def publish_task(
        self,
        job_id: str,
        article_id: str,
        url: str,
        source: str,
        category: str,
        priority: int = 1,
        retry_count: int = 0
    ) -> str:
        """Publish a single scraping task to the appropriate priority queue."""
        task_id = generate_task_id()

        task = {
            "task_id": task_id,
            "job_id": job_id,
            "article_id": article_id,
            "url": url,
            "source": source,
            "category": category,
            "priority": priority,
            "retry_count": retry_count
        }

        # Get priority queue name
        queue_name = self._get_priority_queue_name(priority)

        # Push to priority queue (LPUSH for FIFO within priority)
        await self.redis.lpush(queue_name, json.dumps(task))

        return task_id

    async def publish_tasks(
        self,
        job_id: str,
        articles: List[Dict[str, Any]]
    ) -> List[str]:
        """Publish multiple scraping tasks to Redis queues."""
        task_ids = []

        # Group tasks by priority
        for article in articles:
            task_id = await self.publish_task(
                job_id=job_id,
                article_id=article["article_id"],
                url=article["url"],
                source=article["source"],
                category=article["category"],
                priority=article.get("priority", 1)
            )
            task_ids.append(task_id)

        return task_ids

    async def get_queue_length(self, priority: Optional[str] = None) -> int:
        """Get the length of the task queue."""
        if priority:
            queue_name = f"{self.priority_prefix}:{priority}"
            return await self.redis.llen(queue_name)

        # Sum all priority queues
        total = 0
        for p in ["high", "medium", "low"]:
            total += await self.redis.llen(f"{self.priority_prefix}:{p}")
        return total

    async def publish_job_update(
        self,
        job_id: str,
        status: str,
        article_id: Optional[str] = None,
        completed: int = 0,
        failed: int = 0,
        total: int = 0
    ):
        """Publish a job update to the result channel for WebSocket notifications."""
        update = {
            "type": "job_update",
            "job_id": job_id,
            "status": status,
            "article_id": article_id,
            "completed": completed,
            "failed": failed,
            "total": total
        }
        await self.redis.publish(self.result_channel, json.dumps(update))

    async def clear_job_tasks(self, job_id: str) -> int:
        """Remove all pending tasks for a specific job (for cancellation)."""
        removed_count = 0

        for priority in ["high", "medium", "low"]:
            queue_name = f"{self.priority_prefix}:{priority}"

            # Get all tasks from queue
            tasks = await self.redis.lrange(queue_name, 0, -1)

            for task_json in tasks:
                task = json.loads(task_json)
                if task.get("job_id") == job_id:
                    # Remove this task
                    await self.redis.lrem(queue_name, 1, task_json)
                    removed_count += 1

        return removed_count
