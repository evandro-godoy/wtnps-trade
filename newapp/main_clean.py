"""Compatibility wrapper for canonical API entrypoint."""
from __future__ import annotations

from newapp.src.api.main import app, _map_timeframe_to_int


if __name__ == "__main__":
    import uvicorn
    from newapp.configs.config import HOST, PORT, RELOAD

    uvicorn.run(
        "newapp.src.api.main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
    )
