"""Request schemas for API endpoints."""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, HttpUrl


class ArticleInput(BaseModel):
    """Input schema for a single article."""
    url: str = Field(..., description="URL of the article to scrape")
    source: str = Field(..., description="Source name (e.g., TechNews)")
    category: str = Field(..., description="Article category (e.g., AI, ML)")
    priority: int = Field(default=1, ge=1, le=10, description="Priority level (1-10, lower is higher priority)")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class JobSubmitRequest(BaseModel):
    """Request schema for job submission."""
    articles: List[ArticleInput] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of articles to scrape"
    )

    @field_validator('articles')
    @classmethod
    def validate_unique_urls(cls, v: List[ArticleInput]) -> List[ArticleInput]:
        """Validate that URLs are unique within the request."""
        urls = [article.url for article in v]
        if len(urls) != len(set(urls)):
            raise ValueError('Duplicate URLs in request')
        return v


class WebhookConfig(BaseModel):
    """Configuration for webhook notifications."""
    url: str = Field(..., description="Webhook callback URL")
    headers: Optional[dict] = Field(default=None, description="Optional headers to include")
