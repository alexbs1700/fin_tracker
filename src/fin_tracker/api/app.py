"""FastAPI application exposing my finances to the React frontend (Mac and iPhone)."""

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fin_tracker.api.frontend import mount_frontend
from fin_tracker.api.routes import (
    extracts,
    net_worth,
    portfolio,
    projections,
    spending,
    transactions,
)
from fin_tracker.api.security import (
    AccessKeyMiddleware,
    validate_exposure,
)
from fin_tracker.api.store import FinanceDataStore
from fin_tracker.config import (
    API_ACCESS_KEY,
    API_HOST,
    API_PORT,
    PATH_FRONTEND_DIST,
)

# Vite dev server (development only; the built app is served by the API itself)
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(
    store: FinanceDataStore | None = None,
    access_key: str = API_ACCESS_KEY,
    path_frontend_dist: Path | None = PATH_FRONTEND_DIST,
) -> FastAPI:
    """Build the API around a data store.

    Args:
        store: Data source, defaults to the real extracts in ``data/raw``.
        access_key: Key other devices must send; loopback clients never need it.
        path_frontend_dist: Built frontend to serve at ``/``, None to skip it.

    Returns:
        The configured FastAPI app.
    """
    app = FastAPI(title="fin_tracker", version="0.1.0")
    app.state.store = store or FinanceDataStore()
    app.add_middleware(AccessKeyMiddleware, access_key=access_key)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=FRONTEND_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router_module in (
        net_worth,
        transactions,
        spending,
        portfolio,
        extracts,
        projections,
    ):
        app.include_router(router_module.router)

    @app.get("/api/health", tags=["meta"])
    def get_health() -> dict[str, str]:
        """Liveness check."""
        return {"status": "ok"}

    @app.post("/api/reload", tags=["meta"])
    def reload_data() -> dict[str, str]:
        """Re-read the extracts on the next request (after dropping new files in)."""
        app.state.store.reload()
        return {"status": "reloaded"}

    @app.get("/api/session", tags=["meta"])
    def get_session() -> dict[str, bool]:
        """Protected no-op: answers 200 only when this client may read the data."""
        return {"authorized": True}

    # The catch-all frontend route must come after every API route
    if path_frontend_dist is not None:
        mount_frontend(app, path_frontend_dist)
    return app


def run() -> None:
    """Serve API and built app (entry point ``fin-tracker-api``).

    Listens on ``FIN_TRACKER_HOST`` (loopback by default) and refuses to listen
    on the network without an access key.
    """
    validate_exposure(API_HOST, API_ACCESS_KEY)
    uvicorn.run(create_app(), host=API_HOST, port=API_PORT)
