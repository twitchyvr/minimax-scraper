"""Pydantic request/response schemas."""

from datetime import datetime

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


class WsMessage(BaseModel):
    """WebSocket message types."""

    type: str  # progress, log, page_scraped, error, complete
    job_id: str | None = None
    message: str | None = None
    level: str | None = None  # info, warn, error
    scraped: int | None = None
    total: int | None = None
    current_url: str | None = None
    url: str | None = None
    title: str | None = None
    word_count: int | None = None
    status: str | None = None
    total_pages: int | None = None
    output_dir: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "0.1.0"
