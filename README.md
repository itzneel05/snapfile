# snapfile

**Your screenshot graveyard files itself — on your own machine, with Gemma vision.**

Everyone has a folder called `Screenshots` (or `Desktop`, or `img_2026_...`) with
400 images named `Screenshot 2026-10-24 at 11.42.07.png`. You keep taking them
because filing them is a chore, and searching them later is impossible.

`snapfile` looks at each screenshot with a local vision model, works out what it
actually is, gives it a filename you'll recognise in six months, files it into a
sensible folder — and tells you which ones are junk. You never open the folder
again.

```
$ snapfile ~/Screenshots --apply

snapfile :: 5 screenshots :: model gemma3:4b

  [keep]  Screenshot 2026-10-19 at 14.55.02.png
          Pricing Plans - Free and Pro Tiers -> sorted/ui/pricing-plans-free-and-pro-tiers.png
  [junk]  Screenshot 2026-10-20 at 03.07.11.png
          Solid black screen with no visible content (likely accidental capture)
  [keep]  Screenshot 2026-10-21 at 18.03.29.png
          Cloud Storage Invoice - 2026-10 -> sorted/receipt/cloud-storage-invoice-2026-10.png
  [keep]  Screenshot 2026-10-23 at 09.15.44.png
          Incident room Slack conversation - runner issue -> sorted/chat/incident-room-slack-conversation-runner-issue.png

  3 kept (moved), 2 junk, 0 failed
  junk was left untouched; delete it yourself when you're sure:
    del "Screenshot 2026-10-20 at 03.07.11.png"
```

## Quickstart

Requirements: [Ollama](https://ollama.com) and Python 3.9+. Nothing else — no
API keys, no cloud account, zero runtime dependencies.

```sh
ollama pull gemma3:4b        # ~3.4 GB, one time (gemma3:1b / 806 MB also works)
ollama serve                 # if the desktop app isn't already running

pip install -e .
snapfile ./examples/graveyard          # dry run: shows the plan, touches nothing
snapfile ./examples/graveyard --apply   # files the keeps, leaves the junk for you
```

Useful flags: `--model gemma3:1b` (faster/weaker), `--copy` (don't move),
`--limit 10`, `--json` (for scripting), `--out DIR`.

### Web dashboard

```sh
snapfile web ./examples/graveyard      # http://127.0.0.1:8787
```

A local-only UI (binds `127.0.0.1`, refuses anything else) that shows the
verdicts streaming in card by card while Gemma looks at each screenshot, then
files them behind a confirm dialog. One embedded HTML page, no build step, no
CDN, no webfonts — it renders with the Wi-Fi off, because that is the point.

Try it on the bundled graveyard:

```sh
python examples/make_graveyard.py   # regenerates 5 synthetic screenshots
```

## How it works

```
folder ──> scan (.png/.jpg/.jpeg/.webp/.gif/.bmp)
       ──> one Ollama /api/generate call per image (base64, local HTTP)
              model returns: {kind, title, keep, reason, tags}
       ──> sorted/<kind>/<slug>.png          (keeps)
            report-only                      (junk — never auto-deleted)
```

- **Default is a dry run.** Nothing moves until you pass `--apply`.
- **Junk is never deleted.** `snapfile` only prints the delete commands; a human
  presses enter.
- **Collisions are handled** (`pricing-plans.png` → `pricing-plans-1.png`).
- **The output folder is excluded** from its own rescans.

## Why open innovation matters here

This is a tool that *cannot* be built on a closed API, and that's the whole point:

1. **Your screenshots never leave the laptop.** Screenshots are the most private
   thing on a machine — bank cards, medical portals, private chats, half-written
   messages. A cloud vision API would be the wrong answer even if it were free.
   `snapfile` POSTs to `127.0.0.1:11434` and nowhere else.
2. **It runs with the Wi-Fi off.** Plane, train, airgapped work machine — same
   behaviour, because there is no network dependency to lose.
3. **It costs nothing per look.** Filing 400 screenshots is 400 vision calls.
   At cloud rates that's a decision you'd postpone forever — which is exactly
   how your graveyard got to 400 images. Locally it's a few minutes of GPU and
   then it's over.
4. **You can swap the brain.** `--model` accepts any local vision model. The
   default is Google's open-weight **Gemma 3 4B**; `gemma3:1b` runs on almost
   anything. Fine-tune it on your own screenshots and it gets better at *your*
   desktop, something no closed API will ever let you do.

**The model is load-bearing.** There is deliberately no filename heuristic
fallback: if the model disappears, `snapfile` errors out instead of guessing —
because guessing from filenames is the useless status quo it exists to replace.

## Built with AI

This project was written with AI assistance (OpenCode + Google Gemma 3 running
locally via Ollama), including the research, the code and the demo images.
Disclosed as required by the Hacktoberfest DEV Challenge rules.

## Limitations

- Judgements are model judgements: on a CPU `gemma3:4b` takes roughly 15–25s
  per screenshot, and the verdicts differ slightly between runs. Treat junk
  suggestions as suggestions.
- Still images only (`.png .jpg .jpeg .webp .gif .bmp`), first frame for GIFs.
- Titles come back in English regardless of the screenshot's language.
- No re-run button in the web UI yet — reload the page to triage again.
- The web UI binds loopback only and has no auth; do not expose it.

## Development

```sh
pip install -e ".[dev]"
pytest -q          # 15 tests, no model required
```

## License

[MIT](LICENSE)
