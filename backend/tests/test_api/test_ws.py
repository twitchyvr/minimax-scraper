"""Tests for the WebSocket endpoint."""

import json

from starlette.testclient import TestClient

from app.api.ws import _connections, broadcast
from app.models.schemas import (
    WsCompleteMessage,
    WsErrorMessage,
    WsMessageType,
    WsProgressMessage,
)


class TestWebSocket:
    """Tests for WS /api/ws/{job_id}."""

    def test_connect_and_disconnect(self) -> None:
        from app.main import app

        client = TestClient(app)
        with client.websocket_connect("/api/ws/test-job"):
            # Connection should be tracked
            assert "test-job" in _connections
            assert len(_connections["test-job"]) == 1

        # After disconnect, connection should be cleaned up
        assert "test-job" not in _connections or len(_connections.get("test-job", set())) == 0


class TestBroadcast:
    """Tests for the broadcast helper."""

    async def test_broadcast_no_connections(self) -> None:
        """Broadcasting with no connections should not error."""
        await broadcast("no-such-job", {"type": "progress", "scraped": 1})

    async def test_broadcast_to_connections(self) -> None:
        """Broadcasting should send to all connected clients for a job."""
        from app.main import app

        client = TestClient(app)
        messages: list[dict[str, object]] = []

        with client.websocket_connect("/api/ws/broadcast-test") as ws:
            # Send a broadcast using typed message
            msg = WsProgressMessage(
                job_id="broadcast-test",
                scraped=5,
                total=10,
                current_url="https://example.com/page",
            )
            await broadcast("broadcast-test", msg.model_dump())

            # Receive the message
            data = ws.receive_text()
            messages.append(json.loads(data))

        assert len(messages) == 1
        assert messages[0]["type"] == "progress"
        assert messages[0]["scraped"] == 5
        assert messages[0]["current_url"] == "https://example.com/page"


class TestWsMessageTypes:
    """Tests for typed WebSocket message models."""

    def test_message_type_enum_values(self) -> None:
        """WsMessageType enum has the expected string values."""
        assert WsMessageType.PROGRESS == "progress"
        assert WsMessageType.COMPLETE == "complete"
        assert WsMessageType.ERROR == "error"

    def test_progress_message_serialization(self) -> None:
        """WsProgressMessage serializes with the correct type field."""
        msg = WsProgressMessage(
            job_id="job-1", scraped=3, total=10, current_url="https://example.com"
        )
        data = msg.model_dump()
        assert data["type"] == "progress"
        assert data["job_id"] == "job-1"
        assert data["scraped"] == 3
        assert data["total"] == 10
        assert data["current_url"] == "https://example.com"

    def test_complete_message_serialization(self) -> None:
        """WsCompleteMessage serializes with correct type and fields."""
        msg = WsCompleteMessage(job_id="job-2", total_pages=42, output_dir="/output/job-2")
        data = msg.model_dump()
        assert data["type"] == "complete"
        assert data["total_pages"] == 42
        assert data["output_dir"] == "/output/job-2"
        assert "status" not in data  # removed — Rust side hardcodes this

    def test_error_message_serialization(self) -> None:
        """WsErrorMessage serializes with type and message."""
        msg = WsErrorMessage(job_id="job-3", message="Scrape failed: TimeoutError")
        data = msg.model_dump()
        assert data["type"] == "error"
        assert data["message"] == "Scrape failed: TimeoutError"
