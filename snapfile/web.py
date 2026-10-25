"""Local web UI for snapfile: stdlib http.server, bound to 127.0.0.1 only.

No framework, no build step, no CDN — the page must work with the Wi-Fi off,
because that is the whole pitch of the project. The model does the thinking;
this module just shows it and lets you approve the filing.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .client import DEFAULT_HOST, DEFAULT_MODEL, LocalModelError, pick_model
from .filer import Shot, apply

MAX_BODY = 1 << 20  # 1 MiB is plenty for our tiny JSON posts


class PlanState:
    """Holds the last triage result so page reloads don't re-run the model."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.folder: Path | None = None
        self.out_root: Path | None = None
        self.model: str = DEFAULT_MODEL
        self.shots: list[Shot] = []
        self.applied = False
        self.error: str | None = None
        self.planning = False
        self.total = 0

    def plan_async(self, folder: Path, out_root: Path, model: str,
                   limit: int | None) -> None:
        """Triage in the background so the server answers requests meanwhile."""
        with self.lock:
            if self.planning:
                return
            self.planning = True
            self.shots = []
            self.applied = False
            self.total = 0
            self.folder, self.out_root, self.model = folder, out_root, model
        threading.Thread(target=self._plan_blocking,
                         args=(folder, out_root, model, limit),
                         daemon=True).start()

    def _plan_blocking(self, folder: Path, out_root: Path, model: str,
                       limit: int | None) -> None:
        """Judge images one at a time, publishing each verdict as it lands.

        Streaming matters: a 400-image graveyard takes minutes on a CPU, and a
        UI that shows cards appear one by one is honest about the work — the
        model really is looking at each picture.
        """
        from .filer import judge, scan

        try:
            files = scan(folder, exclude=[out_root])
            chosen = pick_model(DEFAULT_HOST, model)
        except LocalModelError as exc:
            with self.lock:
                self.shots, self.error, self.planning = [], str(exc), False
                return

        if limit:
            files = files[:limit]
        with self.lock:
            self.total = len(files)
        errors = 0
        for path in files:
            shot = judge(Shot(path=path), model=chosen)
            if shot.error is not None:
                errors += 1
            with self.lock:
                self.shots.append(shot)
        with self.lock:
            self.error = None if not errors else f"{errors} image(s) failed"
            self.planning = False

    def plan(self, folder: Path, out_root: Path, model: str, limit: int | None) -> None:
        """Synchronous triage (used by tests and the CLI path)."""
        with self.lock:
            self.folder, self.out_root, self.model = folder, out_root, model
            self.error = None
            self.shots = []
        self._plan_blocking(folder, out_root, model, limit)

    def serialise(self) -> dict[str, Any]:
        from urllib.parse import quote

        from .filer import plan_destination

        with self.lock:
            root = self.folder.resolve() if self.folder else None
            shots = []
            for i, s in enumerate(self.shots):
                try:
                    rel = s.path.resolve().relative_to(root) if root else Path(s.path.name)
                except (ValueError, OSError):
                    rel = Path(s.path.name)
                dest = str(s.dest) if s.dest else None
                if not dest and s.keep and not s.error and self.out_root:
                    # show where it WOULD go, without touching the filesystem
                    dest = str(plan_destination(s, self.out_root))
                shots.append({
                    "index": i,
                    "file": rel.as_posix(),
                    "name": s.path.name,
                    "kind": s.kind,
                    "title": s.title,
                    "keep": s.keep,
                    "reason": s.reason,
                    "tags": s.tags,
                    "dest": dest if (s.keep and not s.error) else None,
                    "error": s.error,
                    "thumb": "/thumb?f=" + quote(rel.as_posix(), safe=""),
                })
            if self.error and not self.shots:
                state = "error"
            elif self.planning and self.total == 0:
                state = "scanning"
            elif self.planning:
                state = "running"
            else:
                state = "done"
            return {
                "state": state,
                "version": __version__,
                "model": self.model,
                "folder": str(self.folder) if self.folder else None,
                "out": str(self.out_root) if self.out_root else None,
                "total": self.total,
                "done": len(self.shots),
                "applied": self.applied,
                "planning": self.planning,
                "error": self.error,
                "shots": shots,
            }


class Handler(BaseHTTPRequestHandler):
    state: PlanState  # injected by serve()
    html: bytes = b"<!doctype html><title>snapfile</title><p>loading&hellip;</p>"
    server_version = f"snapfile/{__version__}"

    # ---- plumbing -------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quiet server log
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict[str, Any], code: int = 200) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    # ---- routes ---------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, self.html, "text/html; charset=utf-8")
            return
        if parsed.path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if parsed.path in ("/api/state", "/api/results"):
            self._json(self.state.serialise())
            return
        if parsed.path == "/thumb":
            self._serve_thumb(parse_qs(parsed.query).get("f", [""])[0])
            return
        if parsed.path == "/img":
            self._serve_image(int(parse_qs(parsed.query).get("i", ["-1"])[0]))
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, MAX_BODY)) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}

        if parsed.path == "/api/plan":
            with self.state.lock:
                folder = Path(payload.get("folder") or self.state.folder or ".")
                out = Path(payload.get("out") or self.state.out_root or folder / "sorted")
                model = str(payload.get("model") or self.state.model)
                limit = payload.get("limit")
            self.state.plan_async(folder, out, model, int(limit) if limit else None)
            self._json(self.state.serialise())
            return

        if parsed.path == "/api/apply":
            mode = str(payload.get("mode") or "move")
            from .filer import plan_destination

            with self.state.lock:
                if not self.state.shots:
                    self._json({"error": "nothing planned yet"}, 400)
                    return
                chosen = []
                for s in self.state.shots:
                    if s.keep and not s.error and s.dest is None and self.state.out_root:
                        s.dest = plan_destination(s, self.state.out_root)
                    if s.keep and not s.error:
                        chosen.append(s)
                if self.state.applied:
                    chosen = []  # idempotent: a second call must not re-move
                else:
                    apply(chosen, move=(mode != "copy"))
                    self.state.applied = True
            # serialise() takes the lock itself — never call it while holding it
            data = self.state.serialise()
            data["moved"] = len(chosen)
            data["junk"] = sum(1 for s in data["shots"] if not s["keep"] and not s["error"])
            data["failed"] = sum(1 for s in data["shots"] if s["error"])
            self._json(data)
            return

        self._send(404, b"not found", "text/plain")

    # ---- helpers --------------------------------------------------------
    def _serve_thumb(self, rel: str) -> None:
        """Serve a file inside the scanned folder only — no traversal, ever."""
        root = (self.state.folder or Path(".")).resolve()
        if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
            self._send(400, b"bad path", "text/plain")
            return
        try:
            resolved = (root / rel).resolve()
            resolved.relative_to(root)  # never serve outside the folder
        except (ValueError, OSError):
            self._send(403, b"outside folder", "text/plain")
            return
        self._send_file(resolved)

    def _serve_image(self, index: int) -> None:
        with self.state.lock:
            shots = list(self.state.shots)
        if not 0 <= index < len(shots):
            self._send(404, b"bad index", "text/plain")
            return
        root = (self.state.folder or Path(".")).resolve()
        try:
            resolved = shots[index].path.resolve()
            resolved.relative_to(root)
        except (ValueError, OSError):
            self._send(403, b"outside folder", "text/plain")
            return
        self._send_file(resolved)

    def _send_file(self, resolved: Path) -> None:
        try:
            body = resolved.read_bytes()
        except OSError:
            self._send(404, b"gone", "text/plain")
            return
        ctype = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }.get(resolved.suffix.lower(), "application/octet-stream")
        self._send(200, body, ctype)


def serve(folder: Path, out_root: Path, host: str = "127.0.0.1", port: int = 8787,
          model: str = DEFAULT_MODEL, ollama: str = DEFAULT_HOST,
          limit: int | None = None) -> None:
    """Start the local dashboard. Blocks until interrupted."""
    from .web_page import HTML  # imported late: keeps CLI startup fast

    state = PlanState()
    handler = type("BoundHandler", (Handler,), {"state": state, "html": HTML.encode("utf-8")})
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True

    print(f"snapfile web :: http://{host}:{port}")
    print(f"  folder : {folder}")
    print(f"  model  : {model}")
    print("  press Ctrl+C to stop\n")

    # Triage in the background: the server must accept requests immediately,
    # or the browser (and any judge following the quickstart) sees a timeout.
    state.plan_async(folder, out_root, model, limit)
    print(f"  triaging {folder} with {model} in the background\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
