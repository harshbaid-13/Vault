# Progress

**Current stage:** S10 (Backup, restore, README) — done; S11 (Hardening) is next
**Last updated:** 2026-09-18, after S10

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
- [x] S2 — Login: `cli set-password`, Argon2id, session + session_version, auth allowlist,
      global lockout, Origin check, safe `next`, logout, Change password in Settings
      (current password required first — TECH_PLAN §5 #23)
- [x] S3 — Phone access: `docs/TAILSCALE.md` (fetched install steps), `tailscale serve`,
      Secure cookie + allowed origin, Settings shows HTTPS ✓ / Clipboard ✓, 2 GB upload probe
- [x] S4 — Clipboard *(reference)*: list, full-screen editor + autosave, hidden, favorite,
      delete, COPY from `.clip__source`; "How a feature is structured" into `CLAUDE.md`
- [x] S5 — Notes (editor, autosave on hide/leave, discard empty) and Links (URL rules, form)
- [x] S6 — Files: raw-body streaming upload (2 parallel), panel, download/view allowlist,
      Range 206, rename, favorite, delete, `?partial=1` refresh
- [x] S7 — Folders: tree, breadcrumb, create/rename/delete with counts, move picker, select
      mode (Move/Delete), per-folder sort
- [x] S8 — Thumbnails (EXIF, bomb limit, HEIC-safe), preview page per kind (PDF iframe on
      desktop, Open/Download on phone), Photos grid by month, viewer with neighbours
- [x] S9 — Home (Favorites 6 + Recent 10), Favorites page, search page + live partial +
      `/api/search`, LIKE escaping, hidden clips title-only
- [x] S10 — `app.backup`: DB snapshot (backup API + integrity check) then copy-if-missing
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
- **S2** — Login. `app/auth.py`: Argon2id hash + `session_version` in `settings`,
  `GET/POST /login` (shows the `set-password` command until a password exists), `POST /logout`,
  `POST /api/password` (current password checked first, counts toward the lockout, keeps this
  session, logs out the rest). `app/cli.py`: `python -m app.cli set-password` (hidden prompt
  twice, ≥ 4 chars, safe while the vault runs — it migrates but never empties `tmp/`).
  `app/security.py`: `LoginLimiter` (one global bucket), `OriginCheckMiddleware` (403; `/api`
  writes must be JSON or octet-stream → 415), `AuthGateMiddleware` (allowlist; pages 302 to
  `/login?next=…`, `/api` 401 JSON). Starlette `SessionMiddleware` cookie `vault_session`.
  Log out in the sidebar, the More sheet and Settings; Settings has Security → Change password
  (a modal) and Log out — the rest of Settings is S3. `app.js`: lockout countdown, password
  form. 109 tests pass (54 new). In Docker: CLI sets the password, redirect/401 when logged
  out, login → `next`, foreign-Origin logout → 403, 5th wrong try → 429 and the right password
  still 429, logout. Headless Firefox (500px — its smallest window — and 1280, light and dark):
  countdown ticks and re-enables, modal errors from client and server, success toast, both
  Log out buttons work, 16px inputs, 44px buttons, no horizontal scroll.
- **S3** — `docs/TAILSCALE.md`: install on Ubuntu 26.04 from Tailscale's apt repo (fetched
  from tailscale.com and pkgs.tailscale.com on 2026-09-17), phone + laptop, rename to
  `office-vault`, disable key expiry, MagicDNS + HTTPS, `sudo tailscale serve --bg 8000`
  (status / off / reset), `.env` changes, why no ports are open, boot checks, troubleshooting.
  Settings is now complete: Vault (storage used · free, file/note/clip/link counts),
  Connection (HTTPS and one-tap copy, checked in the browser), Security (Change password),
  About (version, last backup — "Never" until S10), Log out. Moved to `app/home.py`; `size`
  filter in `web.py`. 114 tests pass. Checked in Docker + headless Firefox: over
  `http://127.0.0.1` Settings shows HTTPS No, one-tap copy Yes (a local address counts as secure).
  Docker was already `enabled` on boot on this computer.
  **Your check (2026-09-17):** Tailscale on the office computer (`office-vault`) and the
  OnePlus phone, `tailscale serve` → `https://office-vault.tail1234.ts.net` (tailnet only),
  `.env` set to that origin + Secure cookie, confirmed by you as working on the phone.

- **S4** — Clipboard. `app/clips.py` (SQL → pages → API): `/clipboard` list (favorites first,
  then newest-modified), `POST /clipboard/new` → full-screen editor `/clipboard/{id}` with
  autosave (800 ms, on hide, on leave), a Hide content switch, ★ in the header, ⋯ Copy all /
  Delete; leaving an empty clip deletes it. `/api/clips` GET `?q=` (title + non-hidden content,
  LIKE escaped), POST, PATCH, DELETE; lengths 200 / 100,000. Rows: title, ★ mark, 3-line
  fading preview or ••••••••, eye for hidden clips, ⋯ (Edit, Favorite, Hide, Delete + confirm),
  COPY from `.clip__source` (the whole text). New shared pieces: `web.ApiError`, `db.like_pattern`,
  `?partial=1` via `{% extends layout %}`, `when` date filter, `macros.html`, `editor.html`,
  delete confirm in `base.html`, `api()` / `refreshMain()` in `app.js`. "How a feature is
  structured" written into `CLAUDE.md`. 150 tests pass (36 new). Headless Firefox (500px, light
  and dark) against a local run: new → type → Saved; hide + star; list masked; COPY on a hidden
  clip and on a 3 KB clip pasted back exactly; reveal; sheet Unhide/Unfavorite refresh the list;
  delete confirm (Cancel focused) from the list and from the editor; empty clip discarded; a
  quick edit then Back shows the new text; no horizontal scroll. Docker image rebuilt and healthy.
  **Your check (2026-09-17):** used on the phone; you saw one clip missing from the list after
  making two (one with only a title or only text). Logs show a clip created and deleted 4 times
  10–16 s later (step 4 of the check does that). Not reproduced in Firefox; you chose to leave it.
- **S5** — Notes and Links, same shape as Clipboard. `app/notes.py`: `/notes` list (rows named
  by the title or the first line, `ago` date · preview line, ★ mark, ⋯ Favorite/Delete),
  `POST /notes/new` → the shared editor with the cursor in the body, autosave as clips, ⋯ Copy
  all / Delete, empty notes discarded; `/api/notes` CRUD + `?q=`, body ≤ 1,000,000.
  `app/links.py`: `normalise_url` (adds `https://`, keeps `host:port`, rejects every other
  scheme and malformed addresses), empty title → host, `/links` list (title opens a new tab
  with `rel="noopener noreferrer"`, mono host · date, description, ⋯ Copy URL/Edit/Favorite/
  Delete), `/links/new` and `/links/{id}/edit` form page, `/api/links` CRUD + `?q=` over title,
  URL and description. Editor pages set `interactive-widget=resizes-content` so the keyboard
  shrinks the page instead of covering the text. Fixed in `app.js`: a ⋯ button carrying
  `data-copy` copied instead of opening its sheet. 214 tests pass (64 new). Headless Firefox
  (500px, light and dark): new note starts in the body; text typed then the page hidden before
  the 800 ms autosave is saved; list row, favorite, delete from the editor; link form rejects
  `javascript:`, `www.irctc.co.in` saves as host title, opens in a new tab, Copy URL pastes back,
  Edit, Delete; no horizontal scroll; the S4 clipboard run still passes. Docker rebuilt, healthy.
  **S5 follow-up (your request):** a **Save** button in the editor header (notes and clips) next
  to ★ and ⋯. It saves now, shows "Saved ✓" for 1.5 s and a "Saved" toast, and stays on the page;
  autosave is unchanged. The link form has a **Use http:// instead of https://** switch: the API
  takes an optional `use_http` with the URL (on → http, off → https, whatever was typed); without
  it, https stays the default. Typing `http://` or `https://` moves the switch to match, and Edit
  shows it on for http links. 222 tests pass. Checked in headless Firefox, light and dark.
  **Waiting for your check on the phone.**

- **S6** — Files. `app/storage.py`: fixed extension → kind/MIME table, the inline allowlist,
  `clean_name` (last segment, no control chars or bidi overrides, trims spaces/dots, 255 chars
  keeping the extension, else "unnamed"), `path_for` (32-hex id only, resolved inside
  `data/files`), `receive_upload` (Content-Length required, limit and disk-space checks first,
  streams to `tmp/<id>.part` in 1 MB writes with sha256, stops the moment the body passes the
  declared or allowed size, fsync + `os.replace`, part file always removed). `app/files.py`:
  `/files` page (newest first, count · total size, rows with type icon, middle-truncated name,
  size · date, ★, ⋯ Download / Rename / Copy name / Favorite / Delete), `POST /api/files`
  (raw body + `X-File-Name`), `GET /api/files`, `PATCH` (name re-reads the type, favorite),
  `DELETE` (row, then bytes; missing bytes → warning by id), `/download` (always attachment,
  `filename*` for non-ASCII) and `/view` (inline only for the allowlist, text as `text/plain`);
  file responses get `sandbox` CSP, nosniff and `private, no-cache`; PDFs `frame-ancestors 'self'`
  + SAMEORIGIN for S8. Range/206 comes from Starlette 1.6's `FileResponse` — tested. `app.js`:
  the real upload (XMLHttpRequest, 2 at a time, progress, cancel aborts, Retry, "Too large (max
  N)" before sending using the server's limit, list refreshes after each upload, leaving asks
  first), drag-and-drop overlay, Rename modal (selects the name without the extension), Download
  via a `download` link so uploads keep going. 280 tests pass (58 new). Headless Firefox: 4 files
  picked (one too large → failed row, rest listed with exact sizes), Hindi name, drop a file,
  rename, view, delete with confirm; three 1 GB files uploaded 2 at a time, one cancelled mid-way
  (tmp/ empty, 2 stored), server memory 53 → 59 MB, downloaded 1 GB byte-identical, a Range in
  the middle of it correct. Docker rebuilt, healthy; `/data/files` writable by uid 1000.
  **Your check (2026-09-17):** "working great". You didn't say whether the 2 GB upload over
  `tailscale serve` was part of it, so that stays under Known issues until confirmed.

- **S7** — Folders. `app/folders.py` (split from `files.py` as TECH_PLAN §1 allows): folder SQL
  (recursive CTEs for the breadcrumb, subtree, summary), `/api/folders` GET/POST/PATCH (rename,
  move; into itself or a sub-folder → 422; same name in the same parent, any case → 409),
  `/api/folders/{id}/summary`, `DELETE /api/folders/{id}` (rows in one transaction, then the bytes
  of every file inside), `POST /api/move` (all or nothing) and `POST /api/delete`. `files.py`:
  `/files?folder=<id>&sort=<s>` (bad or missing folder → 404 page), folders first then files,
  sort saved on the folder (top level in `settings.files_sort`), `/api/files?folder_id=&sort=`,
  uploads into `?folder_id=` (checked before the bytes arrive; folder deleted mid-upload → 404 and
  the bytes removed), `PATCH /api/files/{id}` takes `folder_id`. Page: back button + breadcrumb
  (`<h1>` is the folder name), sort sheet (Name, Date added, Size, Type; tapping the current one
  flips it), count line, a "Filter this folder" box, folder rows (item count, ⋯ Rename / Move /
  Delete), Move added to the file ⋯. Header ⋯: New folder, Select. Select mode: checkboxes (always
  shown at 900px+, where ticking one starts it; Shift-click ticks a range), tapping a row ticks it,
  top bar "N selected · Select all", bottom bar Move / Delete. Move picker: a sheet that starts in
  this folder, walks the tree, hides the folders being moved, "Move here". Delete confirms name
  what goes: "Delete Tax? The 3 folders and 42 files inside will be deleted too." / "Delete 1
  folder and 2 files?". 338 tests pass (58 new, `tests/test_folders.py`). Headless Firefox against
  a local run: at 500px created Documents → Bills → 2026 from the UI, uploaded 6 files into 2026,
  back button → Bills, browser Back → 2026, Select → ticked 5 → Move → up to Bills → Move here
  ("Moved 5 files to Bills"), filter, Largest first, deleted 2026 with its file, renamed a folder
  (whole name selected), duplicate name error in the form, no horizontal scroll; at 1280px ticked
  one checkbox, Shift-clicked a range of 4, moved them with the picker, bulk-deleted a folder + a
  file. Logs show ids and counts only. Docker image **not** rebuilt (your vault container is running).

  **Your check (2026-09-17):** "done cool".

- **S8** — Previews, thumbnails, Photos. `app/thumbs.py`: Pillow (already an approved dependency),
  first request makes `data/thumbs/<id>.webp` (400px long side, WebP q80), JPEG `draft()` decode,
  `exif_transpose`, 80 MP limit checked from the header plus Pillow's own bomb error, at most two
  decodes at once, written via `tmp/` + rename. Anything that fails leaves `<id>.none` and the
  route 404s (logged by id and exception type only). `GET /api/files/{id}/thumb` (`private,
  max-age=604800`, sandbox CSP). Thumbnails go with their file on single, folder and bulk delete.
  `/files/{id}` preview page: image; PDF iframe (only where there's a mouse; app.js sets `src`
  there, so a phone never loads it) plus Open PDF; video/audio players (`preload="metadata"`);
  text ≤ 1 MB escaped in a scroll box with COPY; everything else (incl. HTML/SVG/HEIC) "No preview
  for this type." Details line (`PDF · 16 KB · Added Today, 18:14`) with Copy name, Download; ★ in
  the header, ⋯ Rename / Move / Copy name / Delete (back to the folder). File and folder rows now
  open the preview and have a 40px icon box, images with a thumbnail over it; move picker and
  Rename modal moved into `file_dialogs.html`. `app/photos.py`: `/photos` images + videos from
  every folder, newest first, month headings in VAULT_TIMEZONE, 60 per page with a
  `?before=<created_at>,<id>` cursor, the next page loaded as the "Load more" link nears the screen
  (a month split over two pages joins up). `/photos/{id}` viewer page: that photo ± 10 neighbours
  as a scroll-snap strip; swipe / ← → / on-screen arrows; the address, title, ★ and ⋯ follow the
  slide; reaching an edge slide with more beyond reloads around it; ‹, ✕ and Esc go back in history
  to the grid (scroll kept) or to `/photos`; ⋯ Download / Rename / Copy link ("Link copied. It only
  works when logged in to your vault.") / Delete (then the next photo). Videos play in the slide
  (`preload="none"`); HEIC shows "No preview" + Download. 380 tests pass (42 new:
  `test_thumbs.py`, `test_photos.py`). Headless Firefox with 74 generated files (70 JPEGs, a 12 MP
  JPEG with EXIF orientation 6, a fake HEIC, a PDF, a text file): grid 60 → 72 after scrolling,
  HEIC tile shows its icon, rotated thumbnail is portrait, viewer → ArrowRight changes address and
  menu, delete moves to the next, Esc back to `/photos`, Files rows with thumbnails, PDF on a
  500px window shows Download + Open PDF with no frame loaded, text preview escaped, at 1280px the
  PDF renders in the frame (Firefox), rename and ★ from the preview. No horizontal scroll.
  Not tried: a real video (no ffmpeg here to make one; Range/206 is tested since S6), Chrome.
  Docker image not rebuilt.

  **Your check (2026-09-18):** "done cool".

- **S9** — Home, Favorites, Search, in `app/home.py` (it combines the per-type queries; files and
  folders gained `search_files` / `search_folders`). **Home** `/`: Favorites (six, clips first, then
  newest-modified; "See all" / "See all N") and Recent (ten newest of any type: files and links by
  when added, notes and clips by last edit; empty ones left out), a hint when nothing is starred, and
  an empty state with Upload a file / New clip. **Favorites** `/favorites?type=`: grouped Files ·
  Notes · Clips · Links with counts, type chips (links, so the choice survives refresh and Back).
  **Search** `/search?q=&type=&in=`: the field is the page's header (Back goes to where you came
  from), results grouped with counts, ≤ 20 per type, folders with files, note snippet around the
  match, clips with COPY right in the results, hidden clips matched by title only and shown
  ••••••••; live as you type (250 ms, from 2 characters, stale answers dropped, address kept in
  step), Enter = the same page, ✕ clears. The search icon on Files/Photos/Notes/Clipboard/Links
  opens it narrowed to that type (`?in=`), "All" widens. `/api/search?q=&type=` returns
  `{folders, files, notes, clips, links}` with a hidden clip's content blanked. Mixed lists use one
  `any_row` macro and a new `clip_compact` row (title opens the editor, COPY above it). Every ⋯
  sheet now comes from `sheets.html` macros (Files, Notes, Links, Clipboard, preview, viewer
  switched to them; `file_dialogs.html` and the S1 placeholder page are gone). Icons in note, link
  and clip rows sit in the same 40px box as file rows so mixed lists line up. 408 tests pass (28 new:
  `test_search.py`, Home/Favorites in `test_home.py`). Headless Firefox at 500px: Home shows the
  hidden Wi-Fi clip, COPY → "Copied ✓" and Ctrl+V pasted `mango-rain-4471`; typing "bill" found the
  Bills folder, the PDF and the note live, with the cursor kept; Notes chip; ✕; search opened from
  Notes started on Notes; Favorites grouped, Unfavorite from ⋯ refreshed it. At 1280px "/" focused
  the header field and Enter opened `/search?q=bill`. No horizontal scroll. Docker not rebuilt.

  **Your check (2026-09-18):** "works great".

- **S10** — Backup, restore, README. `app/backup.py` (`python -m app.backup`): snapshot with
  SQLite's online backup API into `backups/db/vault-YYYY-MM-DD_HHMM.db` (a second run in the same
  minute gets `-2`), switched to a single self-contained file (no -wal/-shm), `PRAGMA
  integrity_check`, then copy-if-missing of every file the snapshot names into
  `backups/files-mirror/<id[:2]>/<id>` via `.part` + fsync + rename with its sha256 checked;
  free space checked against the bytes to copy; any gap → `…-INCOMPLETE.db`, exit 1; keeps the
  newest BACKUP_KEEP (30). `--verify` re-hashes the mirror against the snapshots' hashes;
  `--prune-mirror` deletes mirror files no kept snapshot names. `app/restore.py`
  (`python -m app.restore [snapshot]`, lists without a name): checks the snapshot and that every
  file it needs is in the mirror at the right size before touching anything, then moves the
  current data into `data/before-restore-<time>/`, copies the snapshot in and only the files it
  names (hash-checked); any failure part-way puts the old data back. Refuses `-INCOMPLETE`
  snapshots. Output is ids, counts and sizes only. `backup.sh` (`docker compose exec -T`, sets PATH
  for cron). Settings → Last backup ignores incomplete snapshots. README rewritten for a
  non-developer: Docker install (fetched from docs.docker.com on 2026-09-18: apt repo,
  `docker.sources`, docker group, `systemctl enable docker/containerd`), first setup, start/stop,
  phone access (→ TAILSCALE.md), password, update, backup (nightly cron line, weekly rsync to an
  external drive, monthly `--verify`, `--prune-mirror`), restore (incl. a new computer),
  troubleshooting (all eight from the brief and more), structure, why these technologies.
  424 tests pass (16 new, `tests/test_backup.py`: round trip, empty-folder restore, pruning,
  incomplete, damaged source/mirror, refuse-before-touching, rollback, verify, prune-mirror,
  backup during an open write). **Docker check** in a throw-away container (not your vault):
  note + 300 KB file → backup → delete the note → stop → `docker compose run`-style restore →
  start → the note and file are back, `--verify` OK, files owned by uid 1000. Your vault's
  image was not rebuilt.

## Next
S11 — Hardening: route/escape/log audit, orphan check, 375/768 QA, seed 2,000 files, fresh-install
run of the README.

## Known issues
- **Restore can't tell whether the vault is still running.** The README says `docker compose down`
  first; restoring under a running vault would leave it holding the moved-aside database until
  its next request. S11 could add a check.
- **Cron not set up by me.** Add the `crontab -e` line from the README (section 7) and check
  `backups/backup.log` the next morning.
- **Not checked in S8, please check on your devices:** a video playing and seeking on the phone,
  a real Android camera photo's rotation (thumbnail and viewer), the PDF frame in **Chrome** on the
  laptop (TECH_PLAN gotcha 7), and how fast the grid feels over Tailscale the first time (thumbnails
  are made on first view, two at a time; later views come from the browser cache).
- **The viewer reloads every ~10 swipes** (it's sent 10 neighbours each side). A short flash, then
  swiping carries on from the same photo.
- **Thumbnails that failed once stay failed** (`<id>.none`). If a future Pillow learns a format,
  delete `data/thumbs/*.none` to retry.
- **`static/js/app.js` is 1,400 lines**, past TECH_PLAN §9's "one JS file until ~1,000 lines".
  Not split in S7 (not asked). Splitting per feature is a no-build change for S11 if you want it.
- **Checked-then-filtered rows stay selected.** Typing in the filter hides rows but keeps their
  ticks, so Move/Delete act on hidden rows too (the count says how many). Select all only ticks
  what is shown.
- **The move picker lists every folder from one request** (`/api/folders`). Fine for hundreds of
  folders; revisit only if the tree gets huge.
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
- **To verify, not assumed:** `tailscale serve` passing a 2 GB body (your S6 check), Chrome
  rendering the PDF iframe without a sandbox CSP (S8). Range support: verified in S6.

- **2 GB upload through `tailscale serve` not tested yet** (TECH_PLAN gotcha 19). The route
  exists now: upload a 2 GB file from the laptop over the ts.net address. If it fails or times
  out, lower `MAX_UPLOAD_SIZE_MB` and note why.
- **Upload panel covers the bottom of the list** while it is open (by design, DESIGN §3.13). It
  collapses with ⌄ and hides itself 4 s after everything succeeds; a failed row keeps it open.
- **Not checked at a true 375px in S2.** Headless Firefox won't go below 500px wide. The
  login form is max 360px and the modal is full width minus 16px each side, so it should fit;
  check on the phone in S3 (same for the Settings page).
- **Android back gesture right after typing** (within 0.8 s) can show the list with the old
  text: the editor's save is sent as the page goes away and can land after the list loads.
  Reload shows the new text; nothing is lost. The editor's own ‹ back link waits for the save.
- **A clip went missing from the list on your phone (S4 check), not reproduced.** Suspects: the
  back-gesture race above combined with empty items being left out of lists, or the editor
  seeing its fields as empty on the phone and discarding. Same code runs for notes. If it
  happens again: note which fields had text and how you left the editor.
- **Hidden clips show in plain text in their editor.** Opening the editor is a deliberate tap;
  the list, search and toasts stay masked.
- **Lockout is in memory**, so restarting the container clears it. Fine for one user.

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
- **S2** — "Same error for every failure" means every *wrong* password shows "Wrong password.";
  while locked, the form shows DESIGN §3.1's "Too many attempts. Try again in N seconds." with
  a countdown (429). It says nothing about whether the password was right.
- **S2** — The 5th wrong try starts the 60 s lock at once (so the 6th is blocked). After it
  ends, each further wrong try doubles the lock (120, 240, 480, then 900 s max) until a
  correct login resets it.
- **S2** — The `/api` JSON-only rule applies to POST/PUT/PATCH. DELETE has no body, so it
  only needs the Origin check.
- **S2** — The Change password form is a modal on Settings (not mocked in D3): current, new,
  new again; errors under the fields; "Password changed" toast on success.
- **S2** — `python -m app.cli set-password` runs migrations but not the startup cleanup, so
  running it while the vault is up can't delete an upload in progress.
- **S2** — Minimum password length is **4**, not the playbook's 12 (your call). Accepted
  trade-off: the lockout makes guessing over the network slow, but anyone who gets a copy of
  `vault.db` or a backup could crack a 4-letter hash in hours, so keep backups private.
- **S3** — "Clipboard access" on Settings reads **One-tap copy**: COPY works on plain http too
  (fallback), so the line says what HTTPS actually adds.
- **S3** — HTTPS is checked in the browser (`location.protocol`), not on the server: behind
  `tailscale serve` the app only ever sees plain http, and `X-Forwarded-*` isn't trusted.
- **S3** — Storage "used" is the total size of uploaded files; "free" is free space on the disk
  holding `./data`.
- **S3** — The 2 GB upload probe moves to S6 (needs the upload route).
- **S4** — No search box on the Clipboard page (the brief had one): DESIGN §3.9 has none, search
  is the header 🔍 (S9). `/api/clips?q=` is built and tested.
- **S4** — Starring or hiding a clip doesn't change `updated_at`, so it doesn't jump in the list.
  Only title/content edits count as modified.
- **S4** — Empty clips (no title, no text) never appear in lists: they only exist while their
  editor is open, and the discard on leaving can land after the list has loaded.
- **S4** — A clip with no title shows as "Untitled" (never its content, which may be hidden).
- **S4** — The editor has no tab bar (as the D3 mockup), and its Hide content switch is a
  checkbox at the right of the "Saved" line.
- **S4** — After an autosave the line reads "Saved · Today, HH:MM" (device clock). A failed save
  shows one error toast, "Not saved yet — your text is still here.", and retries every 5 s.
- **S4** — Favorite/Hide from a row's ⋯ show a toast (as the D3 mockup); the editor's ★ doesn't
  (DESIGN §8.15).
- **S5** — Notes list has no search box (as Clipboard, DESIGN §3.7); `/api/notes?q=` is built.
- **S5** — An untitled note's row is named by its first non-empty line, and the preview is the next
  line. Empty notes (no title, no body) are left out of the list, as clips.
- **S5** — New note puts the cursor in the body (brief); new clip keeps it in the title (a clip
  needs a name to find it).
- **S5** — Editor save failure line: "Not saved — retrying… Your text is still here." (brief's
  "Not saved, retrying" plus DESIGN's reassurance). Used by clips too.
- **S5** — Links are ordered favorites first, then newest *saved* (`created_at`, TECH_PLAN index).
  Editing a link doesn't move it.
- **S5** — `host:port` without a scheme (`192.168.1.1:8080`, `localhost:8000`) gets `https://`
  like any other bare address; every other `something:` is rejected. `www.` is dropped from the
  shown host and the auto title.
- **S5** — The link form is its own page without the tab bar (not a sheet), saved with JSON; Save
  returns to Links. No toast, since the page changes.
- **S5 (your call)** — Editors get a Save button after all (DESIGN §3.8 said none): autosave stays,
  Save is for the feel of finishing. It stays on the page; Save on an empty item says "Type
  something first." The header's Save is the editor's one filled button (no COPY on that screen).
- **S5 (your call)** — Links: a "Use http://" switch on the form. Backend default stays https; the
  switch, when sent, sets the scheme even over a typed one, and the form keeps it in sync with
  what you type.
- **S6** — Uploads are one request per file (TECH_PLAN §9), so the brief's "multiple files in one
  request" test is "five files, one request each".
- **S6** — Types come from a fixed extension table in `storage.py`, not Python's `mimetypes`
  (which reads the OS's mime.types, so the container and a local run could disagree). SVG,
  HTML, XML and JS are kind "other".
- **S6** — Display names also lose Unicode bidi overrides (so `photo\u202egpj.exe` can't show as
  `photoexe.jpg`); zero-width joiners stay for Indic names. A cut 300-char name keeps its extension.
- **S6** — Rename to an empty name → 422 "Enter a name." (an upload with no name is "unnamed").
- **S6** — Files list ties (same second) break by upload order (`rowid`), since ids are random.
- **S6** — File responses are `Cache-Control: private, no-cache` (revalidate with ETag), not
  `no-store` like pages: photos and video don't re-download on every view, and nothing is
  shared-cacheable.
- **S6** — No Upload button in the Files header: the sidebar (desktop) and the tab bar (phone)
  already have one on every page.
- **S6** — A dropped folder is skipped; only files upload.
- **S7** — A folder starts sorted by **Name A–Z** (the schema default), so the top level no longer
  lists newest first as S6 did. Date added → newest first on the first tap, Size → largest first.
- **S7** — Folders have no size or type: under those sorts they stay in name order; under Date
  added they sort by when they were made. Folders always come before files.
- **S7** — The brief's filter box is built ("Filter this folder", narrows the rows on screen, no
  request). DESIGN has no such box; the brief asked for it and nothing in TECH_PLAN dropped it.
- **S7** — Folder names are cleaned like filenames, so `Bills/2026` becomes `2026` (the last part).
  An empty name → "Enter a name."
- **S7** — Checkboxes are always shown at 900px and up (DESIGN §4 flow: click, Shift-click, Move),
  not only on hover devices: one breakpoint, as the rest of the CSS.
- **S7** — Unticking the last row ends select mode, as on Android. Escape or ✕ also ends it.
- **S7** — Moving doesn't change `updated_at` (like starring); renaming a folder does.
- **S7** — Bulk delete skips ids that are already gone; bulk move refuses the whole move if any
  item or the destination is gone (404) or a folder name clashes there (409).
- **S7** — Drag-to-move on desktop not built (optional in the brief) → `docs/BACKLOG.md`.
- **S8** — Thumbnails are cached in the browser for a week (`private, max-age=604800`), unlike files
  (`no-cache`): a file's bytes never change, and 60 revalidations per grid page would slow it down.
- **S8** — No "include videos" toggle: videos are always in Photos with a play badge (TECH_PLAN §9).
- **S8** — The viewer is its own page per photo (`/photos/<id>`, TECH_PLAN §3), so the phone's back
  button closing it is ordinary history; swiping updates the address with `replaceState`, so Back
  still goes to the grid in one step.
- **S8** — Preview ⋯ has no Download or Favorite: Download is the page's main button and ★ is in the
  header (D4). The page's header title is the folder (where ‹ goes); the file name is the `<h1>`.
- **S8** — "Pin" in the brief is Favorite (★), as everywhere since D4.
- **S8** — The PDF frame shows only on devices with a mouse (`hover: hover` and `pointer: fine`),
  as gotcha 21 says; a touch laptop without a mouse gets Open PDF.
- **S8** — Text over 1 MB, or not UTF-8 enough to read, shows the details only / replacement marks.
- **S8** — File and folder rows got a 40px icon box so names line up with thumbnail rows.
- **S8** — Select mode on Photos (DESIGN §3.5) not built: not in the brief → `docs/BACKLOG.md`.
- **S9** — Home follows DESIGN §3.2 / TECH_PLAN §9, not the brief: Favorites 6 + Recent 10 (mixed),
  no section tiles, no separate recent files / recent notes lists. "See all" only on Favorites.
- **S9** — Home's Favorites put clips first (Home answers "what can I copy"), then newest-modified.
- **S9** — Type chips are links (`?type=`), not in-page filters, on Favorites and Search. Types are
  Files (incl. folders and photos), Notes, Clips, Links; no separate Photos chip.
- **S9** — The Everywhere/this-section toggle is the chips: opened from a section, search starts
  on that section's chip and "All" widens it.
- **S9** — On Home, Favorites and Search the file and folder ⋯ have no Move (the picker needs the
  item's folder); move from Files or the preview. Compact clip rows have no ⋯: the title opens the
  editor, where ★ and delete are.
- **S9** — No recent searches on the empty search page (DESIGN allows "or nothing at all").
- **S9** — `/api/search` blanks a hidden clip's `content`; the page still carries the full text in
  `.clip__source` for COPY, as every list does (TECH_PLAN §8 gotcha 2).
- **S9** — Queries are cut at 200 characters.
- **S10** — Backups are a files mirror + dated DB snapshots (TECH_PLAN §8 gotcha 16), not the
  brief's `.tar.gz` archives, and keep 30 snapshots, not 14. Restore takes a snapshot name.
- **S10** — Snapshot names use VAULT_TIMEZONE time (what you'd look for), not UTC.
- **S10** — The copy is switched to `journal_mode=DELETE` so each snapshot is one file; the app
  turns WAL back on at start after a restore.
- **S10** — Restore without a name lists the snapshots; `-INCOMPLETE` ones are refused.
- **S10** — Only `backup.sh` (Linux); no Windows `.ps1` — the office computer is Ubuntu.

