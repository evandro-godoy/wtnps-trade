from __future__ import annotations

from fastapi import Request, WebSocket

from newapp.src.api.state import AppStateContainer


def get_state_from_request(request: Request) -> AppStateContainer:
    """Return canonical app state container from HTTP request."""
    return request.app.state.container


def get_state_from_websocket(websocket: WebSocket) -> AppStateContainer:
    """Return canonical app state container from websocket."""
    return websocket.app.state.container
