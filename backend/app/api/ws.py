"""WebSocket endpoint for real-time scrape progress."""

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# Active connections: job_id → set of WebSocket connections
_connections: dict[str, set[WebSocket]] = {}


@router.websocket("/api/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str) -> None:
    """Stream real-time progress events for a scrape job."""
    await websocket.accept()

    if job_id not in _connections:
        _connections[job_id] = set()
    _connections[job_id].add(websocket)

    try:
        # Keep connection alive — listen for client messages (e.g. pings)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _connections.get(job_id, set()).discard(websocket)
        if job_id in _connections and not _connections[job_id]:
            del _connections[job_id]


async def broadcast(job_id: str, message: dict[str, Any]) -> None:
    """Broadcast a message to all WebSocket clients watching a job."""
    connections = _connections.get(job_id, set())
    if not connections:
        return

    payload = json.dumps(message)
    dead: list[WebSocket] = []

    for ws in list(connections):  # snapshot to avoid mutation during iteration
        try:
            await ws.send_text(payload)
        except Exception:  # noqa: BLE001
            dead.append(ws)

    # Clean up disconnected clients
    for ws in dead:
        connections.discard(ws)
