"""Pydantic request/response schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, computed_field


class ScrapeJobCreate(BaseModel):
    """Request to create a new scrape job."""

    url: HttpUrl
    max_depth: int = Field(default=2, ge=0, le=10)
    rate_limit: float | None = Field(default=None, gt=0, le=100)
    ai_organize: bool = True


class ScrapeJobResponse(BaseModel):
    """Response for a scrape job."""

    id: str
    url: str
    status: str
    discovery_method: str | None = None
    total_pages: int
    scraped_pages: int
    output_dir: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage from scraped/total pages."""
        if self.total_pages == 0:
            return 0.0
        return round((self.scraped_pages / self.total_pages) * 100, 1)


class PageResponse(BaseModel):
    """Response for a scraped page."""

    id: str
    url: str
    title: str | None = None
    local_path: str | None = None
    status: str
    word_count: int
    section: str | None = None
    scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class FileTreeNode(BaseModel):
    """Recursive file tree node for the explorer."""

    name: str
    path: str
    is_dir: bool
    children: list["FileTreeNode"] = []
    word_count: int = 0


class WsMessageType(StrEnum):
    """Typed WebSocket message types."""

    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"


class WsProgressMessage(BaseModel):
    """WebSocket progress update during scraping."""

    type: Literal["progress"] = "progress"
    job_id: str
    scraped: int
    total: int
    current_url: str


class WsCompleteMessage(BaseModel):
    """WebSocket job completion notification."""

    type: Literal["complete"] = "complete"
    job_id: str
    total_pages: int
    output_dir: str


class WsErrorMessage(BaseModel):
    """WebSocket job error notification."""

    type: Literal["error"] = "error"
    job_id: str
    message: str


class ChatRequest(BaseModel):
    """Request to ask a question about scraped documentation."""

    question: str = Field(min_length=1, max_length=2000)
    job_id: str
    top_k: int = Field(default=5, ge=1, le=20)


class ChatMessageResponse(BaseModel):
    """A single message in chat history."""

    role: str
    content: str


class ChatResponse(BaseModel):
    """Response from the AI chat."""

    answer: str
    sources: list[str]
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "0.1.0"
