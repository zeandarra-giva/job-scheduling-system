"""Job repository for CRUD operations on Jobs collection."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from shared.utils import generate_job_id, get_utc_now


class JobStatus:
    """Job status constants."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobRepository:
    """Repository for Job CRUD operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.jobs

    async def create_job(
        self,
        total_articles: int,
        new_articles: int,
        cached_articles: int,
        article_ids: List[str] = None
    ) -> Dict[str, Any]:
        """Create a new job record."""
        job_id = generate_job_id()
        now = get_utc_now()

        job = {
            "_id": job_id,
            "status": JobStatus.PENDING,
            "total_articles": total_articles,
            "new_articles": new_articles,
            "cached_articles": cached_articles,
            "completed_count": cached_articles,  # Cached articles are already completed
            "failed_count": 0,
            "article_ids": article_ids or [],
            "created_at": now,
            "updated_at": now,
            "completed_at": None
        }

        await self.collection.insert_one(job)
        return job

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        return await self.collection.find_one({"_id": job_id})

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """Update job status."""
        update = {
            "$set": {
                "status": status,
                "updated_at": get_utc_now()
            }
        }
        if completed_at:
            update["$set"]["completed_at"] = completed_at

        result = await self.collection.update_one(
            {"_id": job_id},
            update
        )
        return result.modified_count > 0

    async def increment_completed(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Increment completed count and return updated job."""
        result = await self.collection.find_one_and_update(
            {"_id": job_id},
            {
                "$inc": {"completed_count": 1},
                "$set": {"updated_at": get_utc_now()}
            },
            return_document=True
        )
        return result

    async def increment_failed(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Increment failed count and return updated job."""
        result = await self.collection.find_one_and_update(
            {"_id": job_id},
            {
                "$inc": {"failed_count": 1},
                "$set": {"updated_at": get_utc_now()}
            },
            return_document=True
        )
        return result

    async def add_article_to_job(self, job_id: str, article_id: str) -> bool:
        """Add an article ID to a job's article_ids array."""
        result = await self.collection.update_one(
            {"_id": job_id},
            {
                "$addToSet": {"article_ids": article_id},
                "$set": {"updated_at": get_utc_now()}
            }
        )
        return result.modified_count > 0

    async def complete_job(self, job_id: str) -> bool:
        """Mark a job as completed."""
        now = get_utc_now()
        result = await self.collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.COMPLETED,
                    "updated_at": now,
                    "completed_at": now
                }
            }
        )
        return result.modified_count > 0

    async def fail_job(self, job_id: str) -> bool:
        """Mark a job as failed."""
        now = get_utc_now()
        result = await self.collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.FAILED,
                    "updated_at": now,
                    "completed_at": now
                }
            }
        )
        return result.modified_count > 0

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's still pending or in progress."""
        result = await self.collection.update_one(
            {
                "_id": job_id,
                "status": {"$in": [JobStatus.PENDING, JobStatus.IN_PROGRESS]}
            },
            {
                "$set": {
                    "status": JobStatus.CANCELLED,
                    "updated_at": get_utc_now()
                }
            }
        )
        return result.modified_count > 0

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status information."""
        job = await self.get_job(job_id)
        if not job:
            return None

        pending = job["total_articles"] - job["completed_count"] - job["failed_count"]

        return {
            "job_id": job["_id"],
            "status": job["status"],
            "total_articles": job["total_articles"],
            "completed": job["completed_count"],
            "failed": job["failed_count"],
            "pending": max(0, pending),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"]
        }

    async def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """List jobs with optional status filter."""
        query = {}
        if status:
            query["status"] = status

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def check_and_update_job_completion(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Check if all articles are processed and update job status accordingly."""
        job = await self.get_job(job_id)
        if not job:
            return None

        total_processed = job["completed_count"] + job["failed_count"]

        if total_processed >= job["total_articles"]:
            # All articles processed
            if job["failed_count"] > 0 and job["completed_count"] == 0:
                # All failed
                await self.fail_job(job_id)
            else:
                # At least some succeeded
                await self.complete_job(job_id)

            return await self.get_job(job_id)

        # Still in progress
        if job["status"] == JobStatus.PENDING:
            await self.update_job_status(job_id, JobStatus.IN_PROGRESS)
            return await self.get_job(job_id)

        return job
