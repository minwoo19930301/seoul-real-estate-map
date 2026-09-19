"""Vercel entry point for the read-only Seoul map API.

Static assets are served by Vercel's CDN.  This function handles only ``/api``
requests and reuses the project's request validation and endpoint router.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

os.environ.setdefault("SEOUL_ALLOW_HOSTED", "1")

from server.app import Handler, TerrainAPI  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
_api = None


def get_api():
    global _api
    if _api is None:
        _api = TerrainAPI(ROOT / "data" / "terrain.sqlite", bookmarks_database=Path(tempfile.gettempdir()) / "seoul-elevation-bookmarks.sqlite")
    return _api


class handler(Handler):
    """Vercel-compatible BaseHTTPRequestHandler for all map API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, api=get_api(), directory=ROOT / "dist", **kwargs)

    def route(self, method):
        # Never fall through to SimpleHTTPRequestHandler: source and static
        # files belong to the Vercel project/CDN, not this API function.
        if not urlsplit(self.path).path.startswith("/api/"):
            self.send_error(404, "API route not found")
            return
        if urlsplit(self.path).path == "/api/bookmarks" or urlsplit(self.path).path.startswith("/api/bookmarks/"):
            self.send_error(405, "Bookmarks are browser-local in hosted mode")
            return
        return super().route(method)

    def do_HEAD(self):
        self.send_error(404, "API route not found")


__all__ = ["handler"]
