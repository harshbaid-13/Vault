# Progress

**Current stage:** S1 (walking skeleton) — done, including the Docker checks
**Last updated:** 2026-09-17, S1 Docker checks

Claude: update this file at the end of every stage. Keep it short.

## Environment

The facts about my setup that every stage needs. This section must survive `/clear` —
do not remove it.

- **Office computer (the server):** Ubuntu 26.04.1 LTS
- **My devices:** Android phone, laptop. No iPhone.
- **Max upload size:** 2 GB
- **For S3 (Tailscale) and S10 (Docker/backup):** fetch the current official install
  instructions for Ubuntu 26.04 from the Tailscale and Docker docs at the time you write
  them. Do not write install steps from memory — they go stale and a wrong `apt` line
  wastes an evening.

## Stages

### Design
- [x] D1 — UX and screen spec → `docs/DESIGN.md` Part 1
- [x] D2 — Visual system → `docs/DESIGN.md` Part 2 + `static/css/tokens.css`
- [x] D3 — Clickable mockups → `/mockups`
- [x] D4 — Design review (repeat until happy)
- [x] D5 — Technical plan → `docs/TECH_PLAN.md`

### Build
Each stage: its playbook prompt, adjusted by `docs/TECH_PLAN.md` §9. Tests pass and the app
runs at the end of every one.
- [x] S1 — Walking skeleton: config (refuses bad SESSION_SECRET), db + `001_initial.sql`,
      base layout from the mockups, `/healthz`, security headers, 404/500, Dockerfile (uid
      1000, tzdata), compose (127.0.0.1, ./data, ./backups), `.env.example`, conftest
- [ ] S2 — Login: `cli set-password`, Argon2id, session + session_version, auth allowlist,
      global lockout, Origin check, safe `next`, logout, Change password in Settings
      (current password required first — TECH_PLAN §5 #23)
- [ ] S3 — Phone access: `docs/TAILSCALE.md` (fetched install steps), `tailscale serve`,
      Secure cookie + allowed origin, Settings shows HTTPS ✓ / Clipboard ✓, 2 GB upload probe
- [ ] S4 — Clipboard *(reference)*: list, full-screen editor + autosave, hidden, favorite,
      delete, COPY from `.clip__source`; "How a feature is structured" into `CLAUDE.md`
- [ ] S5 — Notes (editor, autosave on hide/leave, discard empty) and Links (URL rules, form)
- [ ] S6 — Files: raw-body streaming upload (2 parallel), panel, download/view allowlist,
      Range 206, rename, favorite, delete, `?partial=1` refresh
- [ ] S7 — Folders: tree, breadcrumb, create/rename/delete with counts, move picker, select
      mode (Move/Delete), per-folder sort
- [ ] S8 — Thumbnails (EXIF, bomb limit, HEIC-safe), preview page per kind (PDF iframe on
      desktop, Open/Download on phone), Photos grid by month, viewer with neighbours
- [ ] S9 — Home (Favorites 6 + Recent 10), Favorites page, search page + live partial +
      `/api/search`, LIKE escaping, hidden clips title-only
- [ ] S10 — `app.backup`: DB snapshot (backup API + integrity check) then copy-if-missing
      into `backups/files-mirror` with hash checks, keep 30 snapshots, `--prune-mirror`,
      `--verify`; `app.restore <snapshot>`; `backup.sh`, cron, host rsync to external drive, README
- [ ] S11 — Hardening: route/escape/log audit, orphan check, 375/768 QA, seed 2,000 files,
      fresh-install run of the README

## Done so far
- **D1** — `docs/DESIGN.md` Part 1: UX. Navigation, 14 screens with 375px sketches,
  5 key flows with tap counts, shared interaction patterns, and what v1 leaves out.
  No code written.
- **D2** — `docs/DESIGN.md` Part 2: Visual system. Direction "Paper & Ink", full colour
  system for light and dark (all pairs computed against WCAG AA), type scale, spacing,
  radius-by-hierarchy, touch rules, motion, and 15 components with their states.
  Wrote `static/css/tokens.css` (82 custom properties, no selectors) and vendored 31 Lucide
  icons + LICENSE into `static/icons/`.
- **D3** — 14 static pages in `mockups/`: the 13 from the playbook (`upload-sheet.html` is the
  upload panel + open action sheet) plus `settings.html`, so More → Settings is not a dead
  link. Shared `static/css/app.css` (component classes, flat specificity, imports tokens) and
  `static/js/app.js` (delegated `data-*` handlers, no inline script). Placeholder photos, a
  bill page image and a sample PDF are generated files in `mockups/img` and `mockups/files`.
  Checked in headless Firefox: no horizontal scroll, 44px targets and 16px inputs on every
  page at a true 375px; layouts at 768 and 1280; light and dark; COPY copies the full clip
  over both the Clipboard API and the plain-http fallback; hidden clips copy unrevealed;
  sheets, delete confirm, upload panel, viewer, autosave and filters all work. Not yet
  tried on the real Android phone.
- **D4 round 1** — Claude's own review at a true 375px (light and dark, headless Firefox via
  geckodriver). Fixed: Download on the PDF preview was hidden under the tab bar; the ＋ upload
  button looked like "New"; stars on every clip row; ★ repeated in the header and the ⋯ sheet
  on detail screens; sheets said "Favorite" / "Hide content" even when already on; "Pinned" on
  Home vs "Favorites" everywhere else; back button + breadcrumb trail both going up on a phone;
  a scope toggle on a search opened from Home; the "Uploaded" toast landing on the upload
  panel; a gap splitting each clip's title from its text (clip rows 155 → 143px); a gear icon
  on Change password. `docs/DESIGN.md` updated to match. Phone check: "all working great".
- **D5** — `docs/TECH_PLAN.md`: folder structure (one module per feature, SQL → pages → API),
  STRICT SQLite schema, page + JSON route tables, `.env` settings, 23-item security
  checklist mapped to code and tests, pytest fixtures, reliability rules, 21 gotchas, and a
  table of every place the plan departs from the playbook briefs (§9). Settles the three D3
  questions and the D4 "See all" question. No app code, no new dependencies.

- **D5 review** — Three notes applied: Change password requires the current password
  (TECH_PLAN §5 #23, test specified); backups became a files mirror + dated DB snapshots
  (§8 gotcha 16, `files.sha256` added so backup/restore check contents); mockup drift listed
  under Known issues.
- **S1** — Walking skeleton. `app/`: `config.py` (all §4 settings, refuses a missing/short/
  example SESSION_SECRET without echoing it), `db.py` (folders, empties `tmp/`, WAL, numbered
  migrations in their own transactions), `001_initial.sql` (whole v1 schema), `security.py`
  (headers middleware, pure ASGI), `web.py`, `main.py` (placeholder pages for every section,
  `/healthz`, friendly 404/500 — JSON under `/api`), `__main__.py` (`python -m app`, exit 1
  with one sentence on bad config, no access log). Templates reuse the mockup shell.
  `Dockerfile` (3.12-slim, tzdata, uid 1000), `docker-compose.yml` (127.0.0.1:8000, ./data,
  ./backups, healthcheck), `.env.example`, `.dockerignore`, pinned `requirements*.txt`,
  README stub. `app.js`: the mockup's fake upload never runs inside the app (`body[data-app]`).
  55 tests pass. Ran locally with Python 3.12 and checked at 375px in light and dark.
  **Docker checks (2026-09-17, Docker 29.8.1, Compose v5.5.1):** image builds (251 MB), container
  goes healthy, `/healthz` + pages + static + 404 answer with the security headers; listens on
  127.0.0.1:8000 only; runs as uid 1000 and `./data` files are owned by the host user; tzdata
  works (Asia/Kolkata); `./data` survives `down`/`up` and the migration isn't re-applied; a short
  SESSION_SECRET exits 1 with the one-sentence message. `.env` created with a generated secret.

## Next
S2 — Login, from `docs/PLAYBOOK.md`. Commit S1 first.

## Known issues
- **Auto-restart after a crash not tested.** `restart: unless-stopped` is set; killing PID 1 from
  inside the container is ignored by Linux, and `docker kill` counts as a manual stop.
- **Pages answer GET only, not HEAD** (FastAPI routes). `curl -I` shows 405. Harmless; revisit
  only if something needs HEAD.
- **Starlette warns that its test client wants `httpx2`** instead of `httpx`. Only a warning
  with the pinned versions; decide when upgrading, since swapping is a dependency change.
- **Not mocked, designed in the stage that builds them:** select mode, rename/move/new-link/
  change-password forms, swipe-down to dismiss a sheet, the login error/lockout state, the
  offline banner, loading skeletons.
- **The mockups are out of date in these places. Build from `docs/TECH_PLAN.md` §9, not the
  mockup** (the mockups are not being updated):
  - `preview-pdf.html` shows a rendered page-1 image. **S8 must not build one**: desktop embeds
    the PDF in an iframe; on a phone it's the details block with Download + Open PDF.
  - `photos.html` video tile shows a duration (`0:42`). Real tile: play badge only.
  - `home.html` has "See all" on Recent. Real Home: only on Favorites.
  - `photo-viewer.html` ⋯ sheet has no **Copy link**. The real viewer has it.
  - `note-edit.html` doubles as the clip editor. The real clip editor also has a Hidden switch.
  - `upload-sheet.html` + the fake upload in `app.js`: one file at a time, panel looks like it
    persists. Real: 2 in parallel, and leaving the page while uploading asks first.
  - Select mode (not mocked): the bottom bar is Move / Delete, no Download.
- **To verify, not assumed:** Starlette `FileResponse` Range support (S6), `tailscale serve`
  passing a 2 GB body (S3/S6), Chrome rendering the
  PDF iframe without a sandbox CSP (S8).

## Decisions log
Record any decision that differs from `docs/TECH_PLAN.md`, with one line on why.

- **D1** — P0 skipped: `CLAUDE.md` is the rules file, so every `docs/RULES.md` reference in
  the playbook reads as `CLAUDE.md`.
- **D1** — Mobile tab bar is Home · Files · ＋ · Clipboard · More, with Upload as a raised
  centre button. Photos gives up its slot to Upload: photos arrive more often than they are
  browsed, and Upload had to be one tap from anywhere.
- **D1** — No video thumbnails in v1 (no ffmpeg); videos get an icon with a play badge.
  Backlogged.
- **D1** — No encryption at rest. Files are plain bytes on disk; full-disk encryption on the
  Ubuntu host is the right layer. Recorded in `docs/DESIGN.md` §6 with the reasoning so it
  reads as a decision, not an oversight.
- **D1** — Clips may hold long text (~100 KB cap). Rows show a 2–3 line fading preview, the
  editor is full-screen, and COPY always copies the whole clip — never the preview.
- **D1** — Uploads are not resumable. Stream to disk in chunks; a failure shows the error
  with Retry. Backlogged.
- **D1** — Kept despite there being no iPhone: the non-HTTPS clipboard fallback, EXIF
  rotation on thumbnails (Android rotates too), and HTTP Range responses (every browser
  needs them to seek video). Only HEIC thumbnails are iPhone-specific — backlogged.
- **D2** — Visual direction is "Paper & Ink": warm paper, near-black ink, one deep green
  accent, separation by hairline rules rather than cards and shadows. Chosen so the COPY
  button is the only filled element on a screen — it stands out by isolation, not by being
  loud — and so rows stay compact at 375px.
- **D2** — No web fonts. System sans + `ui-monospace` for data. Zero font bytes, zero
  external requests, instant render offline.
- **D2** — Icons are real Lucide (ISC), fetched once and vendored into `static/icons/` with
  their LICENSE. Nothing is fetched at runtime.
- **D2** — Dark mode via `prefers-color-scheme` only, no switcher.
- **D3** — "Copied ✓" holds for 1.5s. DESIGN Part 1 said 2s, Part 2 said 1.5s; Part 2 is the
  component spec.
- **D3** — On plain http, COPY still copies (hidden-textarea + `execCommand`), so the
  "Select to copy" outline state in DESIGN §8.1 is dropped. The long "press and hold" toast
  only shows if that fallback also fails.
- **D3** — Toast icons take the toast's text colour. `--c-danger` is under 3:1 on the
  inverted toast ground in both schemes, so errors are marked by the icon shape.
- **D3** — Added `--c-on-viewer` to `tokens.css` (text on the always-dark viewer) and
  `static/icons/star-filled.svg` (Lucide star with a fill) for the "on" state.
- **D3** — Icons are CSS masks driven by an `--icon` custom property: no inline SVG, no
  `style=`, and a toggle swaps its icon from CSS alone.
- **D3** — Sheets and the delete confirm are native `<dialog>` (free focus trap, Escape,
  focus return). With a mouse, ⋯ opens an anchored popover; the More tab is always a sheet.
- **D3** — The selected filter chip is ink, not green, to keep the accent for COPY.
- **D3** — The Files root crumb reads "Files", not "Home" as in the D1 sketch — Home is a tab.
- **D3** — `html` has scroll padding for the top bar and tab bar, so a focused COPY button
  never scrolls under either.
- **D4** — The centre tab-bar button shows an upload arrow, not ＋. On Notes, Clipboard and
  Links the header already has ＋ New, and two plus signs doing different things is a trap.
- **D4** — Favorite rule: lists show a read-only ★ mark and offer Favorite/Unfavorite in ⋯;
  detail screens (editor, preview, viewer) have the ★ toggle in the header and not in ⋯. Clip
  rows lose their star button — COPY, eye and ⋯ are enough on every row.
- **D4** — Toggle items in a sheet are labelled by what they will do for that item
  (Unfavorite, Unhide content). The trigger carries `data-favorite` / `data-clip-hidden`.
- **D4** — Home's first section is "Favorites", not "Pinned". One word for one idea.
- **D4** — On a phone the Files header is back button + folder name; the breadcrumb trail
  is desktop-only.
- **D4** — Search scope chips only appear when search is opened from a section.
- **D4** — No "Uploaded" toast; the panel's "All uploaded" title is the confirmation.
- **D4** — PDF preview image is capped at 42dvh on a phone so Download is on the first screen.
- **D4** — The PDF preview's ⋯ sheet drops Download (it is the page's main button).
- **D5** — Every departure from the playbook briefs is in `docs/TECH_PLAN.md` §9 rather than
  repeated here. The big ones: `favorite` column (not `pinned`); one raw-body request per
  uploaded file (not multipart); global login lockout (all requests share the proxy's
  address); upload panel does not survive leaving the page; backups are one files mirror + dated DB
  snapshots (files never change after upload, so bytes are copied once — changed in review);
  PDF on phone = Open/Download, no page-1 render; hidden clip content stays in the page;
  "See all" on Recent removed; Change password also in Settings.
