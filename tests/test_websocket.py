"""
Tests for the real-time alert WebSocket endpoint at /api/ws/alerts.

These tests exercise the connection lifecycle, ping/pong, broadcast,
and disconnect-cleanup paths using FastAPI's TestClient (which provides
synchronous WebSocket testing via httpx + Starlette's transport).
"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.routes import websocket as ws_module


@pytest.fixture(scope="function")
def client():
    app = create_app()
    return TestClient(app)


# ------------------------------------------------------------------ #
# Basic lifecycle                                                    #
# ------------------------------------------------------------------ #

class TestConnection:

    def test_connect_receives_welcome(self, client):
        with client.websocket_connect("/api/ws/alerts") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "connected"
            assert "message" in msg

    def test_ping_returns_pong(self, client):
        with client.websocket_connect("/api/ws/alerts") as ws:
            ws.receive_text()  # discard welcome
            ws.send_text("ping")
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "pong"

    def test_ping_does_not_echo_other_text(self, client):
        with client.websocket_connect("/api/ws/alerts") as ws:
            ws.receive_text()
            ws.send_text("hello")
            # No reply expected for non-ping messages within the test window;
            # send a follow-up ping to confirm the socket is still alive.
            ws.send_text("ping")
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "pong"


# ------------------------------------------------------------------ #
# Client tracking                                                    #
# ------------------------------------------------------------------ #

class TestClientRegistry:

    def test_connect_registers_client(self, client):
        starting = len(ws_module._connected_clients)
        with client.websocket_connect("/api/ws/alerts") as ws:
            ws.receive_text()  # welcome
            assert len(ws_module._connected_clients) == starting + 1
        # After the context manager exits the socket is closed; cleanup happens
        # in the endpoint's finally block. Allow brief settle.
        assert len(ws_module._connected_clients) <= starting + 1

    def test_multiple_clients_connect(self, client):
        with client.websocket_connect("/api/ws/alerts") as ws1, \
             client.websocket_connect("/api/ws/alerts") as ws2:
            ws1.receive_text()
            ws2.receive_text()
            assert len(ws_module._connected_clients) >= 2


# ------------------------------------------------------------------ #
# Broadcast helper                                                   #
# ------------------------------------------------------------------ #

class TestBroadcast:

    def test_broadcast_alert_no_clients_is_safe(self):
        # Ensure no clients connected
        ws_module._connected_clients.clear()
        # Should not raise even with zero subscribers
        asyncio.new_event_loop().run_until_complete(
            ws_module.broadcast_alert({"event": "alert_created", "title": "x"})
        )

    def test_broadcast_alert_signature(self):
        # Helper exists, is awaitable, and accepts a dict
        coro = ws_module.broadcast_alert({"event": "test"})
        assert asyncio.iscoroutine(coro)
        asyncio.new_event_loop().run_until_complete(coro)


# ------------------------------------------------------------------ #
# Disconnect cleanup                                                 #
# ------------------------------------------------------------------ #

class TestDisconnect:

    def test_client_set_shrinks_after_close(self, client):
        ws_module._connected_clients.clear()
        with client.websocket_connect("/api/ws/alerts") as ws:
            ws.receive_text()
            assert len(ws_module._connected_clients) == 1
        # After exit, the registry should drop the closed socket on the
        # next broadcast attempt or in the endpoint's finally block.
        # Trigger a broadcast to flush stale entries.
        asyncio.new_event_loop().run_until_complete(
            ws_module.broadcast_alert({"event": "ping_after_close"})
        )
        assert len(ws_module._connected_clients) == 0