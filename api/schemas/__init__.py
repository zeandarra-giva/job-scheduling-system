# Schemas module
from .requests import ArticleInput, JobSubmitRequest
from .responses import (
    JobSubmitResponse,
    JobStatusResponse,
    ArticleResult,
    FailedArticle,
    JobResultsResponse
)

__all__ = [
    "ArticleInput",
    "JobSubmitRequest",
    "JobSubmitResponse",
    "JobStatusResponse",
    "ArticleResult",
    "FailedArticle",
    "JobResultsResponse"
]
