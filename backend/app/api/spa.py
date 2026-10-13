"""Serving the built single-page app from the API.

In a normal server deployment nginx serves the frontend and proxies ``/api``.
The offline/demo build has no nginx, so the API serves the SPA itself — making
the whole application reachable on one URL and one port.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Static files with history-API fallback.

    A client-side route such as ``/dashboard`` has no file behind it, so a plain
    StaticFiles mount answers 404 on refresh or deep link. Returning ``index.html``
    for unmatched paths lets the router handle it.
    """

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return FileResponse(self._index())
            raise

    def _index(self) -> Path:
        directory = Path(self.directory)
        return directory / "index.html"


def mount_frontend(app: FastAPI, directory: Path) -> bool:
    """Mount the built SPA at ``/`` if it is present.

    Must be called *after* every API route is registered: routes are matched in
    registration order, and this mount would otherwise shadow ``/api/*``,
    ``/health``, ``/ready`` and the docs.
    """
    if not (directory / "index.html").is_file():
        logger.warning("Frontend directory %s has no index.html; not serving the SPA.", directory)
        return False

    app.mount("/", SPAStaticFiles(directory=str(directory), html=True), name="frontend")
    logger.info("Serving the built frontend from %s", directory)
    return True
