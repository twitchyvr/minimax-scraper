"""REST API for scrape job management."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.discovery.engine import discover
from app.models.db import DiscoveredUrl, DiscoveryMethod, JobStatus, Page, PageStatus, ScrapeJob
from app.models.schemas import PageResponse, ScrapeJobCreate, ScrapeJobResponse
from app.scraper.engine import ScrapeProgress, scrape
from app.scraper.fetcher import Fetcher
from app.storage.database import get_session

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Track running tasks so they can be cancelled
_running_tasks: dict[str, asyncio.Task[None]] = {}
_MAX_CONCURRENT_JOBS = 10


@router.post("", response_model=ScrapeJobResponse, status_code=201)
async def create_job(
    body: ScrapeJobCreate,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Create a new scrape job and start it in the background."""
    # Prevent unbounded job creation
    active = sum(1 for t in _running_tasks.values() if not t.done())
    if active >= _MAX_CONCURRENT_JOBS:
        raise HTTPException(status_code=429, detail="Too many active jobs")

    job = ScrapeJob(url=str(body.url), status=JobStatus.PENDING)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Launch the scrape pipeline in the background
    task = asyncio.create_task(_run_job(job.id, str(body.url), body.rate_limit))
    _running_tasks[job.id] = task

    return job


@router.get("", response_model=list[ScrapeJobResponse])
async def list_jobs(
    session: AsyncSession = Depends(get_session),
) -> Any:
    """List all scrape jobs, newest first."""
    result = await session.execute(select(ScrapeJob).order_by(ScrapeJob.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=ScrapeJobResponse)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Get details for a specific job."""
    job = await session.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/pages", response_model=list[PageResponse])
async def get_job_pages(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Get all pages for a specific job."""
    job = await session.get(ScrapeJob, job_id, options=[selectinload(ScrapeJob.pages)])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.pages


@router.delete("/{job_id}", status_code=204)
async def cancel_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Cancel a running scrape job."""
    job = await session.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in (JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Job already {job.status.value}")

    # Cancel the background task if running
    task = _running_tasks.pop(job_id, None)
    if task and not task.done():
        task.cancel()

    job.status = JobStatus.CANCELLED
    await session.commit()


async def _run_job(job_id: str, url: str, rate_limit: float | None) -> None:
    """Execute the full scrape pipeline for a job."""
    from app.storage.database import async_session

    async with async_session() as session:
        job = await session.get(ScrapeJob, job_id)
        if not job:
            return

        try:
            # Phase 1: Discovery
            job.status = JobStatus.DISCOVERING
            await session.commit()

            discovery = await discover(url)

            if not discovery.pages:
                job.status = JobStatus.FAILED
                job.error_message = "No pages discovered"
                await session.commit()
                return

            # Map discovery method
            method_map: dict[str, DiscoveryMethod] = {
                "llms_txt": DiscoveryMethod.LLMS_TXT,
                "sitemap": DiscoveryMethod.SITEMAP,
                "sidebar": DiscoveryMethod.SIDEBAR,
            }
            job.discovery_method = method_map.get(discovery.method)
            job.total_pages = len(discovery.pages)

            # Store discovered URLs
            for page in discovery.pages:
                session.add(
                    DiscoveredUrl(
                        job_id=job_id,
                        url=page.url,
                        source=job.discovery_method or DiscoveryMethod.LLMS_TXT,
                        title_hint=page.title,
                        section_hint=page.section,
                    )
                )
            await session.commit()

            # Phase 2: Scrape
            job.status = JobStatus.SCRAPING
            await session.commit()

            output_dir = settings.output_dir / job_id
            job.output_dir = str(output_dir)

            async def on_progress(progress: ScrapeProgress) -> None:
                """Update job progress in the database."""
                job.scraped_pages = progress.completed
                await session.commit()
                # Also broadcast via WebSocket (imported lazily to avoid circular)
                from app.api.ws import broadcast

                await broadcast(
                    job_id,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "scraped": progress.completed,
                        "total": progress.total,
                        "current_url": progress.current_url,
                    },
                )

            fetcher = Fetcher(
                rate_limit=rate_limit or settings.rate_limit_rps,
                max_concurrent=settings.max_concurrent,
                max_retries=settings.max_retries,
                user_agent=settings.user_agent,
            )

            scrape_result = await scrape(
                discovery=discovery,
                output_dir=output_dir,
                fetcher=fetcher,
                progress_callback=on_progress,
            )

            # Phase 3: Store page results
            for scraped_page in scrape_result.pages:
                session.add(
                    Page(
                        job_id=job_id,
                        url=scraped_page.url,
                        title=scraped_page.title or None,
                        local_path=scraped_page.local_path,
                        status=PageStatus.FAILED if scraped_page.error else PageStatus.CONVERTED,
                        content_hash=scraped_page.content_hash or None,
                        word_count=scraped_page.word_count,
                        section=scraped_page.section or None,
                        scraped_at=datetime.now(UTC),
                        fetch_time_ms=float(scraped_page.fetch_time_ms),
                    )
                )

            job.status = JobStatus.COMPLETE
            job.scraped_pages = scrape_result.succeeded
            await session.commit()

            # Broadcast completion
            from app.api.ws import broadcast

            await broadcast(
                job_id,
                {
                    "type": "complete",
                    "job_id": job_id,
                    "status": "complete",
                    "total_pages": scrape_result.total,
                    "output_dir": str(output_dir),
                },
            )

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            await session.commit()
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            await session.commit()

            from app.api.ws import broadcast

            # Sanitize: don't leak internal details to WS clients
            safe_msg = f"Scrape failed: {type(e).__name__}"
            await broadcast(
                job_id,
                {
                    "type": "error",
                    "job_id": job_id,
                    "message": safe_msg,
                },
            )
        finally:
            _running_tasks.pop(job_id, None)
