"""REST API for browsing scraped files."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ScrapeJob
from app.models.schemas import FileTreeNode
from app.storage.database import get_session

router = APIRouter(prefix="/api/browse", tags=["browse"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB read limit


@router.get("/{job_id}/tree", response_model=list[FileTreeNode])
async def get_file_tree(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Get the file tree for a completed job."""
    job = await session.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.output_dir:
        raise HTTPException(status_code=404, detail="No output directory for this job")

    output_path = Path(job.output_dir)
    if not output_path.is_dir():
        raise HTTPException(status_code=404, detail="Output directory not found on disk")

    return _build_tree(output_path, output_path)


@router.get("/{job_id}/file")
async def get_file_content(
    job_id: str,
    path: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Get raw markdown content for a specific file."""
    job = await session.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.output_dir:
        raise HTTPException(status_code=404, detail="No output directory for this job")

    output_path = Path(job.output_dir)
    file_path = (output_path / path).resolve()

    # Path traversal protection
    if not file_path.is_relative_to(output_path.resolve()):
        raise HTTPException(status_code=403, detail="Path traversal rejected")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if file_path.stat().st_size > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    content = file_path.read_text(encoding="utf-8")
    return {"path": path, "content": content}


def _build_tree(root: Path, current: Path) -> list[FileTreeNode]:
    """Recursively build a file tree from the filesystem."""
    nodes: list[FileTreeNode] = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return nodes

    for entry in entries:
        # Skip hidden files and metadata
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue

        relative = str(entry.relative_to(root))

        if entry.is_dir():
            children = _build_tree(root, entry)
            nodes.append(
                FileTreeNode(
                    name=entry.name,
                    path=relative,
                    is_dir=True,
                    children=children,
                )
            )
        elif entry.suffix == ".md":
            # Estimate word count from file size to avoid reading all files into memory
            # (~5 chars per word on average for English text)
            size = entry.stat().st_size
            word_count = size // 5
            nodes.append(
                FileTreeNode(
                    name=entry.name,
                    path=relative,
                    is_dir=False,
                    word_count=word_count,
                )
            )

    return nodes
