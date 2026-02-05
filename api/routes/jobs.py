"""Job routes for the REST API."""
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
import redis.asyncio as redis

from database.connection import get_db, get_redis
from database.repositories.job_repo import JobRepository, JobStatus
from database.repositories.article_repo import ArticleRepository, ArticleStatus
from api.services.publisher import PublisherService
from api.services.deduplication import DeduplicationService
from api.schemas.requests import JobSubmitRequest
from api.schemas.responses import (
    JobSubmitResponse,
    JobStatusResponse,
    JobResultsResponse,
    ArticleResult,
    FailedArticle,
    JobCancelResponse
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/submit", response_model=JobSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_job(
    request: JobSubmitRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Submit a new scraping job.

    - Validates input
    - Creates job record
    - Checks for existing/cached articles (deduplication)
    - Publishes new tasks to Redis queue
    - Returns job ID and status
    """
    job_repo = JobRepository(db)
    dedup_service = DeduplicationService(db)
    publisher = PublisherService(redis_client)

    # Process articles through deduplication
    new_articles, cached_articles, cached_article_ids = await dedup_service.process_articles(
        request.articles
    )

    total_articles = len(request.articles)
    new_count = len(new_articles)
    cached_count = len(cached_articles)

    # Create job record
    job = await job_repo.create_job(
        total_articles=total_articles,
        new_articles=new_count,
        cached_articles=cached_count,
        article_ids=cached_article_ids
    )

    job_id = job["_id"]

    # Determine initial status
    if new_count == 0:
        # All articles from cache - job is complete
        await job_repo.complete_job(job_id)
        initial_status = JobStatus.COMPLETED
        message = "Job completed - all articles from cache"
    else:
        # Publish new tasks to Redis queue
        await publisher.publish_tasks(job_id, new_articles)

        # Update job status to IN_PROGRESS
        await job_repo.update_job_status(job_id, JobStatus.IN_PROGRESS)
        initial_status = JobStatus.IN_PROGRESS
        message = "Job submitted successfully"

        # Add new article IDs to job
        for article in new_articles:
            await job_repo.add_article_to_job(job_id, article["article_id"])

    # Publish job creation update for WebSocket
    await publisher.publish_job_update(
        job_id=job_id,
        status=initial_status,
        completed=cached_count,
        failed=0,
        total=total_articles
    )

    return JobSubmitResponse(
        job_id=job_id,
        status=initial_status,
        total_articles=total_articles,
        new_articles=new_count,
        cached_articles=cached_count,
        message=message
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get the current status of a job."""
    job_repo = JobRepository(db)

    status_info = await job_repo.get_job_status(job_id)

    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    return JobStatusResponse(**status_info)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get the results of a job including scraped article content."""
    job_repo = JobRepository(db)
    article_repo = ArticleRepository(db)

    job = await job_repo.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    # Get all articles for this job
    articles = await article_repo.get_articles_by_ids(job["article_ids"])

    # Separate successful and failed articles
    successful_results = []
    failed_articles = []

    # Track which articles were from cache (existed before job creation)
    job_created_at = job["created_at"]

    for article in articles:
        if article["status"] == ArticleStatus.SCRAPED:
            # Determine if cached (scraped before job was created)
            cached = article["scraped_at"] and article["scraped_at"] < job_created_at

            successful_results.append(ArticleResult(
                article_id=article["_id"],
                url=article["url"],
                source=article["source"],
                category=article["category"],
                title=article["title"],
                content=article["content"],
                scraped_at=article["scraped_at"],
                cached=cached
            ))
        elif article["status"] == ArticleStatus.FAILED:
            failed_articles.append(FailedArticle(
                url=article["url"],
                error=article["error_message"] or "Unknown error",
                attempted_at=article["updated_at"]
            ))

    return JobResultsResponse(
        job_id=job_id,
        status=job["status"],
        total_articles=job["total_articles"],
        successful=len(successful_results),
        failed=len(failed_articles),
        results=successful_results,
        failed_articles=failed_articles
    )


@router.delete("/{job_id}", response_model=JobCancelResponse)
async def cancel_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Cancel a pending or in-progress job."""
    job_repo = JobRepository(db)
    publisher = PublisherService(redis_client)

    job = await job_repo.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    if job["status"] not in [JobStatus.PENDING, JobStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status {job['status']}"
        )

    # Remove pending tasks from queue
    removed = await publisher.clear_job_tasks(job_id)

    # Cancel the job
    success = await job_repo.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cancel job"
        )

    # Publish cancellation update
    await publisher.publish_job_update(
        job_id=job_id,
        status=JobStatus.CANCELLED,
        completed=job["completed_count"],
        failed=job["failed_count"],
        total=job["total_articles"]
    )

    return JobCancelResponse(
        job_id=job_id,
        status=JobStatus.CANCELLED,
        message=f"Job cancelled. Removed {removed} pending tasks."
    )


@router.get("/", response_model=List[JobStatusResponse])
async def list_jobs(
    status_filter: str = None,
    limit: int = 50,
    skip: int = 0,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """List all jobs with optional status filter."""
    job_repo = JobRepository(db)

    jobs = await job_repo.list_jobs(status=status_filter, limit=limit, skip=skip)

    result = []
    for job in jobs:
        pending = job["total_articles"] - job["completed_count"] - job["failed_count"]
        result.append(JobStatusResponse(
            job_id=job["_id"],
            status=job["status"],
            total_articles=job["total_articles"],
            completed=job["completed_count"],
            failed=job["failed_count"],
            pending=max(0, pending),
            created_at=job["created_at"],
            updated_at=job["updated_at"]
        ))

    return result
