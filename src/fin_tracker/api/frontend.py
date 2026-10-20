"""Serve the built React app (``frontend/dist``) from the API, one port for everything."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_frontend(app: FastAPI, path_dist: Path) -> bool:
    """Serve the built frontend for every non-API path, falling back to ``index.html``.

    The fallback lets client-side routes such as ``/movimientos`` load directly.

    Args:
        app: The API app.
        path_dist: Folder produced by ``npm run build``.

    Returns:
        True if the frontend was mounted, False if it has not been built.
    """
    path_index = path_dist / "index.html"
    if not path_index.exists():
        return False
    path_root = path_dist.resolve()

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_frontend(requested_path: str) -> FileResponse:
        if requested_path.startswith("api/"):
            raise HTTPException(status_code=404)
        path_file = (path_root / requested_path).resolve()
        # Only files inside dist are served (no ../ escapes)
        if (
            requested_path
            and path_file.is_file()
            and path_file.is_relative_to(path_root)
        ):
            return FileResponse(path_file)
        return FileResponse(path_index, headers={"Cache-Control": "no-cache"})

    return True
