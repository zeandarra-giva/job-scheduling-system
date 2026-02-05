"""Article model definitions."""
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ArticleStatusEnum(str, Enum):
    """Article status enumeration."""
    PENDING = "PENDING"
    SCRAPING = "SCRAPING"
    SCRAPED = "SCRAPED"
    FAILED = "FAILED"


class ArticleModel(BaseModel):
    """Article model for database representation."""
    id: str = Field(alias="_id")
    url: str
    source: str
    category: str
    priority: int
    title: Optional[str] = None
    content: Optional[str] = None
    status: ArticleStatusEnum
    error_message: Optional[str] = None
    scraped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reference_count: int = 1
    retry_count: int = 0

    class Config:
        populate_by_name = True
