"""The single-file UI for `snapfile web`.

Contract: docs/UI-SPEC.md. One <style>, one <script>, zero external requests —
the page must render identically with the Wi-Fi off, because that is the whole
argument of the project. Model output is untrusted: everything the model says
reaches the DOM through textContent, never innerHTML.
"""

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>snapfile web</title>
<style>
  :root {
    --bg: #1b1d16;
    --surface: #24271d;
    --inset: #14150f;
    --line: #353929;
    --amber: #e6a54a;
    --amber-hover: #f0b35c;
    --green: #9dbb67;
    --clay: #d08151;
    --dim: #a3a692;
    --text: #eceadd;
    --mono: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--text); }
  body {
    font: 400 15px/1.5 var(--sans);
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 0 32px; }
  a { color: inherit; }

  /* ---- header ---- */
  header {
    position: sticky; top: 0; z-index: 10;
    background: var(--surface);
    border-bottom: 1px solid var(--line);
  }
  .bar {
    display: flex; align-items: center; gap: 16px;
    padding: 16px 0; min-height: 76px;
  }
  .mark { font: 600 18px/1.2 var(--sans); }
  .mark span { color: var(--dim); font: 400 13px/1.4 var(--mono); margin-left: 8px; }
  .pill {
    font: 400 13px/1.4 var(--mono); text-transform: uppercase; letter-spacing: .06em;
    padding: 4px 8px; border-radius: 4px; border: 1px solid var(--amber);
    color: var(--amber);
  }
  .pill.applied { border-color: var(--green); color: var(--green); }
  .bar .count { color: var(--dim); font-size: 13px; }
  .bar .spacer { flex: 1; }

  /* ---- buttons ---- */
  button {
    font: 600 15px/1.5 var(--sans);
    border-radius: 8px; min-height: 44px; padding: 0 24px;
    cursor: pointer; border: 1px solid transparent;
  }
  .primary { background: var(--amber); color: #1b1d16; }
  .primary:hover:not([disabled]) { background: var(--amber-hover); }
  .primary:focus-visible { outline: 2px solid #eceadd; outline-offset: 2px; }
  .primary[disabled] { opacity: .5; cursor: default; }
  .secondary {
    background: transparent; color: var(--text);
    border-color: var(--line); font-weight: 400;
  }
  .secondary:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }

  /* ---- summary strip ---- */
  .summary { padding: 32px 0 0; }
  .summary h1 {
    margin: 0; font: 400 15px/1.5 var(--sans);
    color: var(--text);
  }
  .summary .folder {
    display: block; margin-top: 4px;
    font: 400 13px/1.4 var(--mono); color: var(--dim);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .reassure { color: var(--dim); font-size: 13px; }
  .status {
    margin-top: 8px;
    font: 400 13px/1.4 var(--mono); color: var(--dim);
  }
  .banner {
    margin-top: 8px;
    font: 400 13px/1.4 var(--mono); color: var(--green);
  }

  /* ---- grid ---- */
  main { padding: 48px 0 0; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 24px;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
    display: flex; flex-direction: column;
    animation: rise 200ms ease-out both;
  }
  @keyframes rise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
  .thumb {
    display: block; height: 150px; background: var(--inset);
    text-decoration: none;
  }
  .thumb img {
    width: 100%; height: 100%; object-fit: contain; display: block;
  }
  .body { padding: 16px; display: flex; flex-direction: column; gap: 8px; }
  .badges { display: flex; gap: 8px; flex-wrap: wrap; }
  .badge {
    font: 400 13px/1.4 var(--mono); text-transform: uppercase; letter-spacing: .06em;
    padding: 2px 8px; border-radius: 4px; border: 1px solid var(--line);
    color: var(--dim);
  }
  .badge.keep { color: var(--green); background: rgba(157,187,103,.12); border-color: transparent; }
  .badge.junk { color: var(--dim); border-color: var(--dim); }
  .badge.failed { color: var(--clay); border-color: var(--clay); }
  .title {
    margin: 0; font: 600 15px/1.5 var(--sans);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; word-break: break-word;
  }
  .reason {
    margin: 0; font-size: 13px; line-height: 1.4; color: var(--dim);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .path {
    font: 400 13px/1.4 var(--mono); color: var(--green);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .path.muted { color: var(--dim); }
  .path.bad { color: var(--clay); }
  .footnote-line { font-size: 13px; color: var(--dim); }

  /* ---- skeleton ---- */
  .skeleton .sk {
    background: #2c2f24; border-radius: 4px; height: 13px;
    animation: pulse 2400ms ease-in-out infinite;
  }
  .skeleton .sk.thumb-sk { height: 150px; border-radius: 0; }
  .skeleton .body { gap: 8px; }
  @keyframes pulse { 0%,100% { opacity: .6; } 50% { opacity: 1; } }

  /* ---- states ---- */
  .state {
    max-width: 560px; margin: 0 auto; text-align: left;
    padding: 48px 0;
  }
  .state h2 { font: 600 26px/1.2 var(--sans); margin: 0 0 16px; }
  .state.error h2 { color: var(--clay); }
  .state p { margin: 0 0 16px; color: var(--dim); }
  .cmd {
    display: block; background: var(--inset); padding: 8px; border-radius: 4px;
    font: 400 13px/1.4 var(--mono); color: var(--text); margin-bottom: 16px;
    overflow-x: auto;
  }

  /* ---- footnote + footer ---- */
  .footnote {
    margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--line);
    font-size: 13px; color: var(--dim);
  }
  footer {
    margin-top: 64px; padding: 24px 0 48px;
    font: 400 13px/1.4 var(--mono); color: var(--dim);
    border-top: 1px solid var(--line);
  }

  /* ---- dialog ---- */
  dialog {
    background: var(--surface); color: var(--text);
    border: 1px solid var(--line); border-radius: 8px;
    max-width: 440px; width: calc(100% - 48px); padding: 24px;
  }
  dialog::backdrop { background: rgba(0,0,0,.6); }
  dialog h2 { font: 600 18px/1.2 var(--sans); margin: 0 0 16px; }
  dialog p { margin: 0 0 24px; color: var(--dim); }
  dialog .caution { color: var(--clay); font-size: 13px; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }

  @media (max-width: 640px) {
    .wrap { padding: 0 24px; }
    .grid { grid-template-columns: 1fr; }
    .bar { flex-wrap: wrap; }
  }
  @media (prefers-reduced-motion: reduce) {
    .card, .skeleton .sk { animation: none; }
  }
</style>
</head>
<body>
<header>
  <div class="wrap bar">
    <div class="mark">snapfile<span>web</span></div>
    <div class="pill" id="pill">DRY RUN</div>
    <div class="count" id="hcount"></div>
    <div class="spacer"></div>
    <button class="primary" id="cta" disabled>File them</button>
  </div>
</header>

<div class="wrap summary">
  <h1 id="counts">Looking at your screenshots…</h1>
  <span class="folder" id="folder"></span>
  <div class="reassure" id="reassure">Dry run — nothing has moved yet.</div>
  <div class="status" id="status" aria-live="polite"></div>
  <div class="banner" id="banner" aria-live="polite" hidden></div>
</div>

<main class="wrap">
  <div class="grid" id="grid" role="list"></div>
  <div id="state"></div>
  <div class="footnote" id="footnote" hidden>Junk was left untouched — delete it yourself when you're sure.</div>
</main>

<footer>
  <div class="wrap">slow and steady — runs on your machine, with the Wi-Fi off</div>
</footer>

<dialog id="confirm" aria-modal="true" aria-labelledby="dlg-title" aria-describedby="dlg-body">
  <h2 id="dlg-title">File screenshots?</h2>
  <p id="dlg-body"></p>
  <div class="actions">
    <button class="secondary" id="cancel" autofocus>Cancel</button>
    <button class="primary" id="proceed">File them</button>
  </div>
</dialog>

<script>
(function () {
  "use strict";
  var grid = document.getElementById("grid");
  var stateBox = document.getElementById("state");
  var pill = document.getElementById("pill");
  var cta = document.getElementById("cta");
  var counts = document.getElementById("counts");
  var hcount = document.getElementById("hcount");
  var folderEl = document.getElementById("folder");
  var statusEl = document.getElementById("status");
  var banner = document.getElementById("banner");
  var footnote = document.getElementById("footnote");
  var reassure = document.getElementById("reassure");
  var dlg = document.getElementById("confirm");
  var dlgTitle = document.getElementById("dlg-title");
  var dlgBody = document.getElementById("dlg-body");

  var latest = null;
  var applied = false;
  var filing = false;
  var timer = null;
  var rendered = -1; // how many shots are already in the DOM

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; // never innerHTML
    return n;
  }

  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

  function tally(data, kind) {
    return data.shots.filter(function (s) {
      return kind === "keep" ? (s.keep && !s.error)
           : kind === "junk" ? (!s.keep && !s.error)
           : !!s.error;
    }).length;
  }

  function shotCard(s) {
    var card = el("article", "card");
    card.setAttribute("role", "listitem");

    var link = el("a", "thumb");
    link.href = s.thumb;
    link.target = "_blank";
    link.rel = "noopener";
    var img = document.createElement("img");
    img.src = s.thumb;
    img.alt = s.file + " — thumbnail";
    img.loading = "lazy";
    link.appendChild(img);
    card.appendChild(link);

    var body = el("div", "body");
    var badges = el("div", "badges");
    badges.appendChild(el("span", "badge", s.kind.toUpperCase()));
    badges.appendChild(el("span", "badge " + (s.error ? "failed" : s.keep ? "keep" : "junk"),
      s.error ? "FAILED" : s.keep ? "KEEP" : "JUNK"));
    body.appendChild(badges);

    var t = el("h2", "title", s.error ? s.name : s.title);
    body.appendChild(t);

    if (s.error) {
      body.appendChild(el("p", "reason", "The model couldn't read this one."));
      var first = String(s.error).split("\n")[0];
      body.appendChild(el("div", "path bad", first));
      body.appendChild(el("div", "footnote-line", "Skipped — nothing else changed."));
    } else {
      body.appendChild(el("p", "reason", s.reason));
      if (s.keep && s.dest) {
        var p = el("div", "path", s.dest);
        p.title = s.dest;
        body.appendChild(p);
      } else {
        body.appendChild(el("div", "path muted", "left where it is"));
      }
    }
    card.appendChild(body);
    return card;
  }

  function skeletons(n) {
    grid.textContent = "";
    for (var i = 0; i < n; i++) {
      var c = el("article", "card skeleton");
      c.setAttribute("role", "listitem");
      c.appendChild(el("div", "sk thumb-sk"));
      var b = el("div", "body");
      var sk1 = el("div", "sk"); sk1.style.width = "40%";
      var sk2 = el("div", "sk"); sk2.style.width = "85%";
      var sk3 = el("div", "sk"); sk3.style.width = "65%";
      b.appendChild(sk1); b.appendChild(sk2); b.appendChild(sk3);
      c.appendChild(b);
      grid.appendChild(c);
    }
  }

  function showState(kind, data) {
    grid.textContent = "";
    stateBox.textContent = "";
    var box = el("div", "state" + (kind === "error" ? " error" : ""));
    if (kind === "empty") {
      box.appendChild(el("h2", null, "Nothing to file."));
      box.appendChild(el("p", null,
        "snapfile found no screenshots in " + (data.folder || "this folder") +
        ". Drop in some .png or .jpg files, then reload this page."));
    } else if (kind === "model") {
      box.appendChild(el("h2", null, "No vision model installed."));
      box.appendChild(el("span", "cmd", "ollama pull gemma3:4b"));
      box.appendChild(el("p", null, "Pull it, then reload this page."));
    } else {
      box.appendChild(el("h2", null, "Can't reach Ollama."));
      box.appendChild(el("p", null,
        "snapfile needs your local model to look at screenshots. Nothing has run yet."));
      box.appendChild(el("span", "cmd", "ollama serve"));
      box.appendChild(el("p", null, "Start it, then reload this page."));
    }
    stateBox.appendChild(box);
  }

  function ctaLabel(n, keeps) {
    if (applied) return ["Filed", true];
    if (filing) return ["Filing…", true];
    if (keeps === 0) return ["Nothing to file", true];
    return [n === 1 ? "File it" : "File them", false];
  }

  function render(data) {
    latest = data;
    applied = !!data.applied;
    var total = data.total || 0;
    var done = data.done || 0;
    var keeps = tally(data, "keep");
    var junk = tally(data, "junk");
    var failed = tally(data, "failed");
    var n = data.shots.length;
    var busy = data.state === "scanning" || data.state === "running";

    document.title = "snapfile web — " +
      (data.folder ? data.folder.split(/[\\/]/).filter(Boolean).pop() : "screenshots");
    folderEl.textContent = data.folder || "";
    folderEl.title = data.folder || "";

    pill.textContent = applied ? "APPLIED" : "DRY RUN";
    pill.className = "pill" + (applied ? " applied" : "");

    if (busy && n === 0) {
      counts.textContent = "Reading the folder…";
      hcount.textContent = "";
    } else if (applied) {
      counts.textContent = keeps + " filed (moved) · " + junk + " junk left untouched · " + failed + " failed";
      hcount.textContent = plural(n, "screenshot");
    } else {
      counts.textContent = plural(n, "screenshot") + " · " + keeps + " keep · " +
        junk + " junk · " + failed + " failed";
      hcount.textContent = plural(n, "screenshot");
    }

    reassure.hidden = applied;
    statusEl.textContent = busy
      ? done + " of " + total + " looked at · model " + data.model + " · no rush"
      : "";
    if (applied) {
      banner.hidden = false;
      banner.textContent = keeps + " filed (moved) · " + junk + " junk left untouched · " + failed + " failed";
    }

    footnote.hidden = !(junk > 0);

    var label = ctaLabel(n, keeps);
    cta.textContent = label[0];
    cta.disabled = applied || filing || keeps === 0 || busy;

    // states
    if (data.state === "error") { showState(/no vision model|not installed/i.test(data.error || "") ? "model" : "unreachable", data); return; }
    if (!busy && n === 0) { showState("empty", data); return; }
    stateBox.textContent = "";

    // grid
    if (n === rendered) return;
    if (n < rendered) { grid.textContent = ""; rendered = -1; }
    if (rendered === -1) { grid.textContent = ""; }
    for (var i = Math.max(rendered, 0); i < n; i++) grid.appendChild(shotCard(data.shots[i]));
    rendered = n;
  }

  function poll() {
    fetch("/api/results", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        render(data);
        var busy = data.state === "scanning" || data.state === "running";
        if (busy && !applied) {
          if (rendered === -1 || data.shots.length === 0) skeletons(6);
          timer = setTimeout(poll, 1500);
        } else if (!applied) {
          timer = setTimeout(poll, 4000); // idle refresh until you act
        }
      })
      .catch(function () {
        showState("unreachable", { folder: "" });
        timer = setTimeout(poll, 4000);
      });
  }

  cta.addEventListener("click", function () {
    if (!latest) return;
    var keeps = tally(latest, "keep");
    dlgTitle.textContent = keeps === 1 ? "File 1 screenshot?" : "File " + keeps + " screenshots?";
    dlgBody.textContent = "This moves " + keeps + " kept screenshot" + (keeps === 1 ? "" : "s") +
      " into sorted/. Junk is left untouched — snapfile never deletes anything.";
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
    document.getElementById("cancel").focus();
  });

  document.getElementById("cancel").addEventListener("click", function () { dlg.close(); });

  document.getElementById("proceed").addEventListener("click", function () {
    dlg.close();
    filing = true;
    cta.textContent = "Filing…";
    cta.disabled = true;
    fetch("/api/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "move" })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { filing = false; render(data); })
      .catch(function () { filing = false; showState("unreachable", { folder: "" }); });
  });

  dlg.addEventListener("close", function () { if (!filing) cta.focus(); });

  skeletons(6);
  poll();
})();
</script>
</body>
</html>
"""
