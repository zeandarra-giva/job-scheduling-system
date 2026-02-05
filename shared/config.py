"""Shared configuration for all services."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_queue_name: str = "scraping_tasks"
    redis_priority_queue_prefix: str = "scraping_tasks:priority"
    redis_result_channel: str = "job_updates"

    # MongoDB Configuration
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "job_scheduler"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False

    # Consumer Configuration
    consumer_batch_size: int = 10
    consumer_poll_interval: float = 1.0
    max_retry_attempts: int = 3
    retry_base_delay: float = 1.0
    scrape_timeout: int = 30

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # WebSocket Configuration
    ws_heartbeat_interval: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
