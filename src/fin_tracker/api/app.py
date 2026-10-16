"""FastAPI application exposing my finances to the local React frontend."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fin_tracker.api.routes import (
    extracts,
    net_worth,
    portfolio,
    spending,
    transactions,
)
from fin_tracker.api.store import FinanceDataStore

# Vite dev server; the API only ever listens on localhost
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
API_HOST = "127.0.0.1"
API_PORT = 8000


def create_app(store: FinanceDataStore | None = None) -> FastAPI:
    """Build the API around a data store.

    Args:
        store: Data source, defaults to the real extracts in ``data/raw``.

    Returns:
        The configured FastAPI app.
    """
    app = FastAPI(title="fin_tracker", version="0.1.0")
    app.state.store = store or FinanceDataStore()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=FRONTEND_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router_module in (net_worth, transactions, spending, portfolio, extracts):
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

    return app


def run() -> None:
    """Serve the API on localhost (entry point ``fin-tracker-api``)."""
    uvicorn.run(create_app(), host=API_HOST, port=API_PORT)
