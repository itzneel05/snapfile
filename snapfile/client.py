"""Minimal stdlib-only client for a local Ollama server.

No third-party HTTP library, no API key, no telemetry. By default it talks to
127.0.0.1 only: your screenshots never leave the machine they are filed on.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:4b"
FAST_MODEL = "gemma3:1b"
REQUEST_TIMEOUT = 300


class LocalModelError(RuntimeError):
    """Raised when the local model backend cannot be reached or refuses."""


@dataclass(frozen=True)
class ModelInfo:
    name: str
    size_bytes: int = 0

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024**3)


def _request(host: str, path: str, payload: dict[str, Any] | None = None,
             timeout: int = REQUEST_TIMEOUT) -> Any:
    url = host.rstrip("/") + path
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise LocalModelError(
            f"Could not reach your local Ollama server at {host}.\n"
            f"  -> start it with:  ollama serve\n"
            f"  underlying error: {exc}"
        ) from exc

    if not body.strip():
        return None
    return json.loads(body)


def list_models(host: str = DEFAULT_HOST) -> list[ModelInfo]:
    """Return the models already pulled onto this machine."""
    try:
        raw = _request(host, "/api/tags", timeout=15)
    except LocalModelError:
        return []
    out: list[ModelInfo] = []
    for m in (raw or {}).get("models", []):
        out.append(ModelInfo(name=m.get("name", ""), size_bytes=int(m.get("size", 0))))
    return out


def pick_model(host: str = DEFAULT_HOST, preferred: str | None = None) -> str:
    """Choose a model: explicit choice, else the default, else smallest local model."""
    installed = list_models(host)
    names = [m.name for m in installed]

    if preferred:
        if preferred in names:
            return preferred
        base = preferred.split(":")[0]
        for n in names:
            if n.split(":")[0] == base:
                return n
        raise LocalModelError(
            f"Model '{preferred}' is not installed locally.\n"
            f"  pull it with:  ollama pull {preferred}\n"
            f"  installed: {', '.join(names) or '(none)'}"
        )

    if DEFAULT_MODEL in names:
        return DEFAULT_MODEL
    if not names:
        raise LocalModelError(
            "No local models found. Pull one first, e.g.:\n"
            "  ollama pull gemma3:4b"
        )
    installed.sort(key=lambda m: m.size_bytes)
    return installed[0].name


def encode_image(path: Path) -> str:
    """Read an image file and base64-encode it for the Ollama API."""
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise LocalModelError(f"Could not read image {path}: {exc}") from exc


def generate(host: str, model: str, prompt: str, system: str | None = None,
             images: list[str] | None = None, temperature: float = 0.1) -> str:
    """Single-turn completion. Returns the raw text the model produced."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
    }
    if system:
        payload["system"] = system
    if images:
        payload["images"] = images

    raw = _request(host, "/api/generate", payload)
    if not isinstance(raw, dict) or "response" not in raw:
        raise LocalModelError(f"Unexpected response from Ollama: {raw!r}")
    if raw.get("error"):
        raise LocalModelError(str(raw["error"]))
    return str(raw["response"])


def generate_json(host: str, model: str, prompt: str, system: str | None = None,
                  images: list[str] | None = None,
                  temperature: float = 0.1) -> dict[str, Any]:
    """Completion that expects a JSON object back; repairs common model slop."""
    text = generate(host, model, prompt, system=system, images=images,
                    temperature=temperature)
    return parse_json_object(text)


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output.

    Models wrap JSON in prose or ```json fences. This pulls the object out
    without pulling in a third-party parser.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()

    start = stripped.find("{")
    if start == -1:
        raise LocalModelError(f"Model returned no JSON object:\n{text[:400]}")

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start: idx + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break

    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise LocalModelError(f"Could not parse model JSON:\n{text[:400]}")
