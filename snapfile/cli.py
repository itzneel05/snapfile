"""Command line interface for snapfile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .client import DEFAULT_HOST, DEFAULT_MODEL, LocalModelError
from .filer import Shot, apply, run

MARK_KEEP = "[keep]"
MARK_JUNK = "[junk]"
MARK_FAIL = "[fail]"


def _web_main(argv: list[str]) -> int:
    """`snapfile web` — local dashboard for triaging a screenshot folder."""
    p = argparse.ArgumentParser(
        prog="snapfile web",
        description="Local web dashboard (127.0.0.1 only, no CDN, works offline).",
    )
    p.add_argument("folder", nargs="?", default=".", type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--bind", default="127.0.0.1",
                   help="interface to bind (default: 127.0.0.1 — never expose this)")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--ollama", default=DEFAULT_HOST, dest="ollama")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args(argv)

    if not args.folder.exists():
        print(f"error: no such folder: {args.folder}", file=sys.stderr)
        return 2
    if args.bind not in ("127.0.0.1", "localhost", "::1"):
        print("refusing to bind a non-loopback interface — this UI has no auth",
              file=sys.stderr)
        return 2

    from .web import serve
    out_root = args.out or (args.folder / "sorted")
    serve(args.folder, out_root, host=args.bind, port=args.port,
          model=args.model, ollama=args.ollama, limit=args.limit)
    return 0


def _fmt_row(shot: Shot) -> str:
    if shot.error:
        marker, detail = MARK_FAIL, (shot.error.splitlines() or ["error"])[0][:70]
    elif shot.keep:
        marker, detail = MARK_KEEP, f"{shot.title} -> {shot.dest}"
    else:
        marker, detail = MARK_JUNK, f"{shot.title} ({shot.reason})"
    return f"  {marker:7} {shot.path.name}\n          {detail}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="snapfile",
        description="Your screenshot graveyard files itself — locally, with Gemma vision.",
        epilog=(
            "By default snapfile only shows what it would do. "
            "Pass --apply to actually move files."
        ),
    )
    p.add_argument("folder", nargs="?", default=".", type=Path,
                   help="folder of screenshots to triage (default: current directory)")
    p.add_argument("--out", type=Path, default=None,
                   help="output folder (default: <folder>/sorted)")
    p.add_argument("--apply", action="store_true",
                   help="perform the filing (default is a dry run)")
    p.add_argument("--copy", action="store_true",
                   help="copy files instead of moving them")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"local vision model (default: {DEFAULT_MODEL})")
    p.add_argument("--host", default=DEFAULT_HOST,
                   help=f"Ollama host (default: {DEFAULT_HOST})")
    p.add_argument("--limit", type=int, default=None,
                   help="only triage the first N screenshots")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="emit machine-readable JSON instead of a table")
    p.add_argument("--version", action="version", version=f"snapfile {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `snapfile web [folder]` starts the local dashboard.
    if argv and argv[0] == "web":
        return _web_main(argv[1:])

    args = build_parser().parse_args(argv)

    folder: Path = args.folder
    if not folder.exists():
        print(f"error: no such folder: {folder}", file=sys.stderr)
        return 2
    out_root: Path = args.out or (folder / "sorted")

    try:
        shots = run(folder, out_root, host=args.host, model=args.model,
                    limit=args.limit)
    except LocalModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not shots:
        print(f"no screenshots found under {folder}")
        return 0

    if args.apply:
        shots = apply(shots, move=not args.copy)

    kept = [s for s in shots if s.keep and not s.error]
    junk = [s for s in shots if not s.keep and not s.error]
    failed = [s for s in shots if s.error]
    verb = ("copied" if args.copy else "moved") if args.apply else "would be filed"

    if args.as_json:
        print(json.dumps({
            "model": args.model,
            "applied": bool(args.apply),
            "shots": [s.as_dict() for s in shots],
        }, indent=2))
        return 0 if not failed else 1

    print(f"\nsnapfile :: {len(shots)} screenshots :: model {args.model}\n")
    for shot in shots:
        print(_fmt_row(shot))
    print(
        f"\n  {len(kept)} kept ({verb}), {len(junk)} junk, {len(failed)} failed"
        + ("" if args.apply else "   <- dry run, add --apply to file them")
    )
    if junk:
        print("  junk was left untouched; delete it yourself when you're sure:")
        for s in junk:
            print(f"    del \"{s.path}\"")
    print()
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
