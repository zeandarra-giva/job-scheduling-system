"""Job model definitions."""
from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class JobStatusEnum(str, Enum):
    """Job status enumeration."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobModel(BaseModel):
    """Job model for database representation."""
    id: str = Field(alias="_id")
    status: JobStatusEnum
    total_articles: int
    new_articles: int
    cached_articles: int
    completed_count: int
    failed_count: int
    article_ids: List[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
