"""SQLAlchemy database models."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""


class JobStatus(enum.StrEnum):
    """Status of a scrape job."""

    PENDING = "pending"
    DISCOVERING = "discovering"
    SCRAPING = "scraping"
    ORGANIZING = "organizing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PageStatus(enum.StrEnum):
    """Status of an individual page scrape."""

    PENDING = "pending"
    FETCHING = "fetching"
    FETCHED = "fetched"
    CONVERTED = "converted"
    FAILED = "failed"


class DiscoveryMethod(enum.StrEnum):
    """How pages were discovered."""

    LLMS_TXT = "llms_txt"
    SITEMAP = "sitemap"
    SIDEBAR = "sidebar"
    SINGLE_PAGE = "single_page"


class ScrapeJob(Base):
    """A scrape job targeting a documentation site."""

    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    discovery_method: Mapped[DiscoveryMethod | None] = mapped_column(
        Enum(DiscoveryMethod), nullable=True
    )
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    scraped_pages: Mapped[int] = mapped_column(Integer, default=0)
    output_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    pages: Mapped[list["Page"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Page(Base):
    """A scraped documentation page."""

    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("scrape_jobs.id"))
    url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[PageStatus] = mapped_column(Enum(PageStatus), default=PageStatus.PENDING)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[str | None] = mapped_column(String(256), nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetch_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    job: Mapped["ScrapeJob"] = relationship(back_populates="pages")


class DiscoveredUrl(Base):
    """A URL discovered during the discovery phase."""

    __tablename__ = "discovered_urls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("scrape_jobs.id"))
    url: Mapped[str] = mapped_column(String(2048))
    source: Mapped[DiscoveryMethod] = mapped_column(Enum(DiscoveryMethod))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    title_hint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    section_hint: Mapped[str | None] = mapped_column(String(256), nullable=True)

    job: Mapped["ScrapeJob"] = relationship(back_populates="discovered_urls")
