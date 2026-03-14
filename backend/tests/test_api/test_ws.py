"""Tests for the WebSocket endpoint."""

import json

from starlette.testclient import TestClient

from app.api.ws import _connections, broadcast


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
            # Send a broadcast
            await broadcast("broadcast-test", {"type": "progress", "scraped": 5, "total": 10})

            # Receive the message
            data = ws.receive_text()
            messages.append(json.loads(data))

        assert len(messages) == 1
        assert messages[0]["type"] == "progress"
        assert messages[0]["scraped"] == 5
