"""The filing core: look at a screenshot, decide what it is, file it.

This is the part that cannot work without a model. There is deliberately no
heuristic fallback: if the vision model goes away, snapfile stops rather than
guessing from filenames like "Screenshot 2026-10-24 at 11.42.07.png" — which
is exactly the useless naming that created your graveyard in the first place.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

from .client import DEFAULT_HOST, DEFAULT_MODEL, encode_image, generate_json, pick_model

SYSTEM_PROMPT = (
    "You are a meticulous screenshot librarian working entirely on the user's "
    "own machine. You look at an image, work out what it actually is, give it "
    "a filename a human would recognise six months from now, and say whether "
    "it is worth keeping at all. You are concise, you never invent details "
    "that are not visible in the image, and you reply with a single JSON "
    "object and nothing else."
)

KINDS = ("code-error", "ui", "doc", "chat", "receipt", "meme", "photo", "other")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

SYSTEM_DIRS = {"sorted", "_sorted", "organized", "_organized", ".git"}

_PROMPT = """Look at this screenshot and file it.

Reply with exactly one JSON object, no prose, no markdown fence:
{{
  "kind": "one of {kinds}",
  "title": "4 to 8 words describing what is actually shown",
  "keep": true or false,
  "reason": "max 12 words: why keep it, or why it is junk",
  "tags": ["2", "or", "3", "lowercase tags"]
}}

Rules:
- keep=false only for junk: duplicate, accidental capture, blank region,
  pure decoration you would never search for later.
- title must describe the visible content, never the filename.
- kind must be the single best fit from the list.
- HTTP error pages, stack traces and terminal build failures are "code-error",
  not "ui". "ui" means app interfaces, settings screens, dashboards, mockups.
"""


@dataclass
class Shot:
    """One screenshot awaiting a verdict."""
    path: Path
    kind: str = "other"
    title: str = ""
    keep: bool = True
    reason: str = ""
    tags: list[str] = field(default_factory=list)
    dest: Path | None = None
    error: str | None = None

    @property
    def slug(self) -> str:
        return slugify(self.title) or self.path.stem

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["dest"] = str(self.dest) if self.dest else None
        return data


def slugify(text: str) -> str:
    """Filename-safe slug: lowercase, ascii-ish, max 60 chars."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned[:60].rstrip("-")


def scan(folder: Path, exclude: Iterable[Path] = ()) -> list[Path]:
    """All image files in a folder tree, minus the output folder."""
    excluded = {p.resolve() for p in exclude}
    found: list[Path] = []
    for child in sorted(folder.rglob("*")):
        if not child.is_file() or child.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if any(part.lower() in SYSTEM_DIRS for part in child.parts):
            continue
        if any(str(child.resolve()).startswith(str(e) + "/") or
               str(child.resolve()).startswith(str(e) + "\\") or
               child.resolve() == e for e in excluded):
            continue
        found.append(child)
    return found


def plan_destination(shot: Shot, out_root: Path) -> Path:
    """sorted/<kind>/<slug><ext>, with collision handling."""
    ext = shot.path.suffix.lower() or ".png"
    dest = out_root / shot.kind / f"{shot.slug}{ext}"
    if dest.exists() or dest == shot.path.resolve():
        counter = 1
        while True:
            candidate = out_root / shot.kind / f"{shot.slug}-{counter}{ext}"
            if not candidate.exists():
                return candidate
            counter += 1
    return dest


def judge(shot: Shot, host: str = DEFAULT_HOST, model: str | None = None) -> Shot:
    """Ask the local vision model what this screenshot is."""
    chosen = model or pick_model(host)
    try:
        payload = generate_json(
            host, chosen,
            _PROMPT.format(kinds=", ".join(f'"{k}"' for k in KINDS)),
            system=SYSTEM_PROMPT,
            images=[encode_image(shot.path)],
        )
    except Exception as exc:  # noqa: BLE001 - surfaced per-file, never fatal
        shot.error = str(exc)
        return shot

    kind = str(payload.get("kind", "other")).strip().lower()
    if kind not in KINDS:
        kind = "other"
    shot.kind = kind
    shot.title = str(payload.get("title", "")).strip() or shot.path.stem
    shot.keep = bool(payload.get("keep", True))
    shot.reason = str(payload.get("reason", "")).strip()
    raw_tags = payload.get("tags") or []
    if isinstance(raw_tags, list):
        shot.tags = [str(t).strip().lower() for t in raw_tags if str(t).strip()][:4]
    return shot


def run(folder: Path, out_root: Path, host: str = DEFAULT_HOST,
        model: str | None = None, limit: int | None = None) -> list[Shot]:
    """Judge every screenshot in a folder and compute its destination."""
    chosen = model or pick_model(host)
    files = scan(folder, exclude=[out_root])
    if limit:
        files = files[:limit]
    shots = []
    for f in files:
        shot = judge(Shot(path=f), host=host, model=chosen)
        if shot.error is None:
            shot.dest = plan_destination(shot, out_root)
        shots.append(shot)
    return shots


def apply(shots: list[Shot], move: bool = True) -> list[Shot]:
    """Execute the plan: copy or move each kept screenshot into place.

    Screenshots the model marked keep=false are never touched here; they are
    only reported, so a human decides what actually gets deleted.
    """
    for shot in shots:
        if shot.dest is None or shot.error is not None:
            continue
        if not shot.keep:
            continue
        shot.dest.parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(str(shot.path), str(shot.dest))
        else:
            shutil.copy2(str(shot.path), str(shot.dest))
    return shots
