"""Response schemas for API endpoints."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class JobSubmitResponse(BaseModel):
    """Response schema for job submission."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    total_articles: int = Field(..., description="Total number of articles in job")
    new_articles: int = Field(..., description="Number of new articles to scrape")
    cached_articles: int = Field(..., description="Number of cached articles reused")
    message: str = Field(default="Job submitted successfully")


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    total_articles: int = Field(..., description="Total number of articles")
    completed: int = Field(..., description="Number of completed articles")
    failed: int = Field(..., description="Number of failed articles")
    pending: int = Field(..., description="Number of pending articles")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ArticleResult(BaseModel):
    """Schema for a single article result."""
    article_id: str = Field(..., description="Unique article identifier")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="Article source")
    category: str = Field(..., description="Article category")
    title: Optional[str] = Field(None, description="Article title")
    content: Optional[str] = Field(None, description="Scraped article content")
    scraped_at: Optional[datetime] = Field(None, description="Scraping timestamp")
    cached: bool = Field(..., description="Whether article was from cache")


class FailedArticle(BaseModel):
    """Schema for a failed article."""
    url: str = Field(..., description="Article URL")
    error: str = Field(..., description="Error message")
    attempted_at: Optional[datetime] = Field(None, description="Last attempt timestamp")


class JobResultsResponse(BaseModel):
    """Response schema for job results."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    total_articles: int = Field(..., description="Total number of articles")
    successful: int = Field(..., description="Number of successfully scraped articles")
    failed: int = Field(..., description="Number of failed articles")
    results: List[ArticleResult] = Field(default_factory=list, description="Successful article results")
    failed_articles: List[FailedArticle] = Field(default_factory=list, description="Failed articles")


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class JobCancelResponse(BaseModel):
    """Response schema for job cancellation."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="New job status")
    message: str = Field(..., description="Cancellation message")
