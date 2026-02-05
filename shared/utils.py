"""Shared utility functions."""
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return f"job_{uuid.uuid4().hex[:12]}"


def generate_article_id() -> str:
    """Generate a unique article ID."""
    return f"art_{uuid.uuid4().hex[:12]}"


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return f"task_{uuid.uuid4().hex[:12]}"


def get_utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def normalize_url(url: str) -> str:
    """Normalize URL for consistent comparison."""
    parsed = urlparse(url)
    # Remove trailing slash and convert to lowercase
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized.lower()


def url_hash(url: str) -> str:
    """Generate a hash for a URL (for indexing purposes)."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def validate_url(url: str) -> bool:
    """Validate that a URL is properly formatted."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO format string."""
    if dt is None:
        return None
    return dt.isoformat()


def calculate_exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay."""
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)
