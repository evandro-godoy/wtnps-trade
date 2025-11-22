"""Tests for FastAPI WebSocket and HTTP endpoints.

This test module validates the core API functionality:
- Health check endpoint
- Root endpoint
- WebSocket connection, message validation, and error handling
"""
import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Provide TestClient for API testing."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    def test_health_check_returns_ok(self, client: TestClient) -> None:
        """Health check should return 200 with status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "wtnps-trade"
        assert "version" in data

    def test_health_check_response_schema(self, client: TestClient) -> None:
        """Health check response should match HealthStatus schema."""
        response = client.get("/health")
        data = response.json()
        required_keys = {"status", "service", "version"}
        assert required_keys.issubset(data.keys())


class TestRootEndpoint:
    """Test suite for root / endpoint."""

    def test_root_returns_welcome_message(self, client: TestClient) -> None:
        """Root endpoint should return welcome message."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "WTNPS Trade API" in data["message"]


class TestWebSocketEndpoint:
    """Test suite for /ws WebSocket endpoint."""

    def test_websocket_connection_established(self, client: TestClient) -> None:
        """WebSocket should accept connections successfully."""
        with client.websocket_connect("/ws") as websocket:
            # Connection established if context manager doesn't raise
            assert websocket is not None

    def test_websocket_accepts_valid_message(self, client: TestClient) -> None:
        """WebSocket should accept valid ClientMessage and return ACK."""
        with client.websocket_connect("/ws") as websocket:
            valid_message: Dict[str, Any] = {
                "type": "tick",
                "payload": {"price": 123.45, "volume": 1000},
                "timestamp": "2025-11-22T13:30:00Z"
            }
            websocket.send_text(json.dumps(valid_message))
            response = websocket.receive_text()
            assert response == "ACK"

    def test_websocket_accepts_message_without_payload(self, client: TestClient) -> None:
        """WebSocket should accept message with type only (payload optional)."""
        with client.websocket_connect("/ws") as websocket:
            minimal_message: Dict[str, str] = {"type": "heartbeat"}
            websocket.send_text(json.dumps(minimal_message))
            response = websocket.receive_text()
            assert response == "ACK"

    def test_websocket_rejects_invalid_json(self, client: TestClient) -> None:
        """WebSocket should return error for malformed JSON."""
        with client.websocket_connect("/ws") as websocket:
            invalid_json = "{this is not valid json"
            websocket.send_text(invalid_json)
            response = websocket.receive_text()
            assert "ERROR" in response
            assert "invalid JSON" in response

    def test_websocket_rejects_missing_type_field(self, client: TestClient) -> None:
        """WebSocket should return validation error when 'type' field is missing."""
        with client.websocket_connect("/ws") as websocket:
            invalid_message: Dict[str, Any] = {
                "payload": {"data": "some data"},
                # Missing required 'type' field
            }
            websocket.send_text(json.dumps(invalid_message))
            response = websocket.receive_text()
            assert "ERROR" in response
            assert "invalid schema" in response

    def test_websocket_rejects_empty_type_field(self, client: TestClient) -> None:
        """WebSocket should reject messages with empty 'type' field."""
        with client.websocket_connect("/ws") as websocket:
            invalid_message: Dict[str, str] = {
                "type": "",  # Empty string violates min_length=1
            }
            websocket.send_text(json.dumps(invalid_message))
            response = websocket.receive_text()
            assert "ERROR" in response

    def test_websocket_multiple_messages(self, client: TestClient) -> None:
        """WebSocket should handle multiple sequential messages."""
        with client.websocket_connect("/ws") as websocket:
            for i in range(3):
                msg: Dict[str, Any] = {
                    "type": "test",
                    "payload": {"sequence": i}
                }
                websocket.send_text(json.dumps(msg))
                response = websocket.receive_text()
                assert response == "ACK"

    def test_websocket_complex_payload(self, client: TestClient) -> None:
        """WebSocket should accept messages with complex nested payloads."""
        with client.websocket_connect("/ws") as websocket:
            complex_message: Dict[str, Any] = {
                "type": "trade_signal",
                "payload": {
                    "symbol": "WDO$",
                    "action": "BUY",
                    "indicators": {
                        "rsi": 45.2,
                        "macd": {"value": 0.5, "signal": 0.3}
                    },
                    "metadata": ["tag1", "tag2"]
                },
                "timestamp": "2025-11-22T14:00:00Z"
            }
            websocket.send_text(json.dumps(complex_message))
            response = websocket.receive_text()
            assert response == "ACK"


class TestConnectionManager:
    """Test suite for ConnectionManager behavior."""

    def test_multiple_concurrent_connections(self, client: TestClient) -> None:
        """ConnectionManager should handle multiple simultaneous connections."""
        with client.websocket_connect("/ws") as ws1:
            with client.websocket_connect("/ws") as ws2:
                # Both connections active
                msg: Dict[str, str] = {"type": "ping"}
                
                ws1.send_text(json.dumps(msg))
                assert ws1.receive_text() == "ACK"
                
                ws2.send_text(json.dumps(msg))
                assert ws2.receive_text() == "ACK"
