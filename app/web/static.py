"""Serves the built PWA (``frontend/dist``) from the same origin as the API.

- Existing files are served as they are; hashed files under ``assets/`` are cached for a year, everything else
  (``index.html``, ``sw.js``, the manifest) is revalidated on every load so a new deploy is picked up.
- Any other GET outside ``/api/`` returns ``index.html`` so client-side routes deep-link. A missing file
  with an extension is a 404, never ``index.html``: the service worker must not cache HTML as a script.
- ``/api/...`` never falls through to the app shell.
- Paths are resolved and must stay inside the static root (no traversal).
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.web.errors import ApiProblem

log = logging.getLogger(__name__)

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"

# Windows maps some extensions from the registry (.js can come back as text/plain);
# pin the types the PWA uses.
for _type, _ext in (
    ("text/javascript", ".js"),
    ("text/javascript", ".mjs"),
    ("text/css", ".css"),
    ("application/manifest+json", ".webmanifest"),
    ("image/svg+xml", ".svg"),
    ("font/woff2", ".woff2"),
    ("application/json", ".map"),
):
    mimetypes.add_type(_type, _ext)


def _not_found() -> ApiProblem:
    return ApiProblem(404, "not_found", "Not found")


def mount_pwa(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        log.warning("PWA build not found at %s; run `npm run build` in frontend/", root)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def pwa(path: str) -> FileResponse:
        parts = PurePosixPath(path).parts
        if parts[:1] == ("api",):
            raise _not_found()
        if path:
            candidate = (root / path).resolve()
            if not candidate.is_relative_to(root):
                raise _not_found()
            if candidate.is_file():
                cache = IMMUTABLE if parts[:1] == ("assets",) else REVALIDATE
                return FileResponse(candidate, headers={"Cache-Control": cache})
            if "." in parts[-1]:
                raise _not_found()
        if not index.is_file():
            raise ApiProblem(404, "pwa_not_built", "The PWA has not been built")
        return FileResponse(index, headers={"Cache-Control": REVALIDATE})
