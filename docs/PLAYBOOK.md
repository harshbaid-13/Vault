# Personal Vault: Stage-wise Build Playbook

A copy-paste prompt sequence to design and build the vault one working slice at a time. Every stage ends with something you can run and use. Nothing is built "for later."

Replace anything in `[square brackets]` before pasting.

---

## How to use this

1. Create an empty folder `personal-vault/`, run `git init`, and save your original idea document as `docs/SPEC.md`.
2. Use an AI coding tool that can read files and run commands (Claude Code, Cursor, etc.). A plain chat window works too, but you'll be copying files by hand.
3. Run one stage per session. Start every new session with the **Session starter** prompt (Part C), then paste the stage prompt.
4. Don't move to the next stage until the stage's "Done when" checks pass on your real phone. Then `git commit`.
5. When the AI suggests extra features mid-stage, say "add it to docs/BACKLOG.md" and move on.

---

## Decisions already made (so the AI doesn't wander)

**Server-rendered pages, no frontend framework.** FastAPI + Jinja2 templates + a few small vanilla JS files. No React, no npm, no build step. Fewer things to break, nothing to update in a year.

**Built-in `sqlite3`, no ORM.** Six small tables. Plain SQL is easier to read than an ORM for an app this size.

**Uploaded files are saved under random IDs, never under their real name.** The real filename lives only in the database. This removes the whole class of path-traversal bugs instead of trying to filter them. Folders exist only in the database too, so renaming or moving never touches the disk.

**HTTPS through `tailscale serve`.** This one matters more than it looks: the browser Clipboard API only works on HTTPS. If you open the vault at plain `http://office-vault:8000`, the COPY button (the most important feature) will silently fail on phones. Tailscale gives you a real HTTPS address for free, with no ports opened.

**Light security, but not zero.** You're right that this doesn't need enterprise security. We skip user accounts, roles, audit logs, 2FA and token machinery. We keep a handful of cheap basics because the vault will hold things like passport scans and Wi-Fi passwords, and they take minutes now but are painful to add later: Argon2id password hash, login required on every route by default, files stored by random ID, uploaded HTML/SVG never rendered in the browser, and a simple login-attempt limit.

---

## Stage map

| Stage | You get | Size |
|---|---|---|
| P0 | Project rules file | 10 min |
| D1–D5 | UX spec, visual system, clickable mockups, tech plan | 1–2 sessions |
| S1 | App skeleton running in Docker | small |
| S2 | Login and logout | small |
| S3 | Vault reachable from your phone over HTTPS | small (mostly you) |
| S4 | Clipboard with COPY (first useful feature) | medium |
| S5 | Notes with autosave, Links | medium |
| S6 | File upload, download, rename, delete | large |
| S7 | Folders, move, sort | medium |
| S8 | Previews, thumbnails, Photos gallery | large |
| S9 | Home dashboard, Favorites, universal search | medium |
| S10 | Backup, restore, README | medium |
| S11 | Hardening, mobile QA, final checks | medium |

After S4 you already have something you'll use daily. After S6 it replaces "email myself this file."

---

# PART A: Setup and Design

## P0: Project rules file

```text
I'm building a small personal "vault" web app. The full idea is in docs/SPEC.md. Read it.

Create docs/RULES.md: a short rules file (under 60 lines) that every future session will read first. Include:

- Priority order: security basics → reliability → simplicity → everyday usability → visual polish.
- This is a single-user personal utility, not a SaaS. No multi-user, roles, public sharing, cloud services, microservices.
- Stack: Python 3.12, FastAPI, Jinja2 templates, small vanilla JS files, SQLite via built-in sqlite3 (no ORM), Docker Compose. No Node/npm build step, no frontend framework, no CDNs (all assets served locally).
- Do not add a dependency without saying why and asking me.
- Every stage must end with a running app and passing tests. Don't break earlier features.
- Login is required on every route by default. Only /login, /static and /healthz are public.
- User-provided names (filenames, folder names) are display text only and never become filesystem paths.
- No inline JS or inline styles in templates (so a strict Content-Security-Policy works).
- Mobile first: every screen must work at 375px wide.
- Don't expand scope. Put new ideas in docs/BACKLOG.md.
- At the end of every stage, update docs/PROGRESS.md (what's done, what's next, known issues) and give me the exact commands to verify.

Also create empty docs/PROGRESS.md and docs/BACKLOG.md with headings. No app code yet.
```

---

## D1: UX and screen spec

```text
Read docs/RULES.md and docs/SPEC.md.

Act as a product designer who makes small, calm personal utilities (think a good notes app or a clean file manager), not enterprise dashboards. Write docs/DESIGN.md "Part 1: UX". No code.

Include:

1. The 3 things I'll do most often, ranked. My guess: (a) copy a saved text like a Wi-Fi password on my phone, (b) send a photo or file from phone to vault, (c) find something I uploaded recently. Design decisions should favour these.

2. Navigation:
   - Desktop: left sidebar.
   - Mobile: bottom tab bar, maximum 5 items. Decide which 5 and where the rest go.
   - Where Upload and Search live on each. Upload must be reachable in one tap from anywhere.

3. Screen list. For each screen: purpose, what's on it, primary action, secondary actions, empty-state message, and how it looks at 375px (a small ASCII sketch is fine).
   Screens: Login, Home, Files (inside a folder), File preview, Photos grid, Photo viewer, Notes list, Note editor, Clipboard, Links, Favorites, Search results, Upload progress panel, Settings/About.

4. Key flows as numbered steps with tap counts:
   - Phone photo → vault
   - Copy Wi-Fi password on phone
   - Save a link from phone
   - Find a PDF uploaded last week
   - Move 5 files into a folder on desktop

5. Interaction patterns used everywhere:
   - How the "more actions" menu works on touch (bottom sheet) vs mouse
   - Confirmations only for destructive actions
   - Toasts ("Copied ✓", "Uploaded", "Deleted")
   - Loading, error and offline states
   - Clipboard items can be marked "hidden" so the content shows as •••••• until tapped (for passwords when someone is looking at my screen)

6. What we are deliberately NOT designing in v1.

Keep it tight: short bullets, no filler, readable in 10 minutes. If something important is genuinely unclear, ask me at most 3 questions at the end.
```

---

## D2: Visual system

```text
Read docs/RULES.md, docs/SPEC.md and docs/DESIGN.md.

Now define the look. The app is a private utility I'll open many times a day, mostly on my phone. It should feel calm, fast and trustworthy, like a well-made tool, not a marketing site.

Step 1: Propose 3 genuinely different visual directions, a few lines each: mood, 4–6 named hex colours, typeface(s), and one signature detail. Avoid the generic AI-app look: purple/blue gradients, glassmorphism, identical rounded cards with the same soft shadow everywhere, emoji as icons, ALL-CAPS labels above every heading. Recommend one and say why it fits this app specifically.

Step 2: For the recommended direction, add "Part 2: Visual system" to docs/DESIGN.md and create static/css/tokens.css with CSS custom properties:

- Colours for light AND dark mode (via prefers-color-scheme): background, surface, raised surface, border, text (primary, secondary, muted), accent, text-on-accent, success (for "Copied ✓"), danger, focus ring. Text must meet WCAG AA contrast.
- Typography: system font stack or one font we can self-host (no Google Fonts requests). Type scale, weights, line heights. A readable monospace for clipboard content and URLs.
- Spacing scale (4px base), border radius by hierarchy (not one radius for everything), borders, shadows (subtle or none).
- Touch rules: tap targets at least 44×44px, form inputs at least 16px font size (prevents iPhone auto-zoom), bottom nav respects iPhone safe-area insets.
- Icons: one consistent SVG line icon set with a permissive licence (e.g. Lucide), copied into static/icons. List the ~25 icons we need.
- Motion: only in response to my actions (open, close, copied). Respect prefers-reduced-motion.

Step 3: Specify these components with their states (default, hover, pressed, focus, disabled):
primary / secondary / ghost / danger buttons, icon button, COPY button (with 1.5s "Copied ✓" state), text input, textarea, search field, list row, file row, photo tile, bottom tab bar, sidebar, breadcrumb, action bottom sheet, modal, toast, upload progress row, empty state, pin indicator.

The COPY button is the signature element of this app. Make it obvious and thumb-friendly without being loud.
```

---

## D3: Clickable mockups

```text
Read docs/RULES.md, docs/DESIGN.md and static/css/tokens.css.

Build clickable static HTML mockups in /mockups. Plain HTML, one shared CSS file (static/css/app.css, importing tokens.css), and a tiny JS file. No frameworks, no CDNs.

Use realistic fake data: "Wi-Fi Password", "Bank IFSC code", passport.pdf, electricity-bill-aug.pdf, vacation photos (use simple generated placeholder images, not stock photo URLs), a shopping-list note, a few saved links.

Pages:
login.html, home.html, files.html (inside a folder, with breadcrumb), preview-pdf.html, photos.html, photo-viewer.html, notes.html, note-edit.html, clipboard.html, links.html, favorites.html, search.html, plus one page showing the upload progress panel and the action bottom sheet open.

Requirements:
- Mobile first. Check at 375px, 768px and 1280px widths.
- Bottom tab bar on mobile, sidebar on desktop.
- COPY buttons really copy and show "Copied ✓". Use navigator.clipboard when available, with the hidden-textarea fallback so it also works on plain http during mockup testing.
- Hidden clipboard items show •••••• with a reveal button.
- Dark mode works.
- Links between pages work.

This CSS will be reused directly in the real app, so write clean, well-named component classes. Keep selector specificity flat so styles don't fight each other.

When done, tell me how to view them on my phone: run `python -m http.server 8080` from the project root, then open http://[office-computer-LAN-IP]:8080/mockups/home.html on the same Wi-Fi. (Only fake data is involved, so this temporary LAN access is fine. Stop the server afterwards.)
```

---

## D4: Design review (repeat until happy)

```text
Review the mockups as a demanding senior product designer. Assume the screen is 375px wide and the user is on their phone, in a hurry, with one hand.

For each page, list the real problems only:
- tap targets too small or too close
- unclear hierarchy (what's the main action?)
- too many visible actions
- confusing labels or icons
- inconsistent spacing, alignment or type
- dark mode issues
- anything that will be annoying the 100th time I use it

Then fix what matters and tell me what you changed. Do not add features.

My own feedback after using them on my phone:
[write what felt wrong, slow, ugly or confusing]
```

---

## D5: Technical plan

```text
Read docs/RULES.md, docs/SPEC.md, docs/DESIGN.md and look at /mockups.

Act as a senior backend engineer who likes boring, maintainable code. Write docs/TECH_PLAN.md. No app code yet.

Decisions already made (keep them unless you see a real problem, in which case tell me before changing):
- FastAPI + Jinja2 server-rendered pages. Pages render data on the server. All changes (create, update, delete, pin, upload) go through JSON endpoints under /api/, called by small vanilla JS files.
- SQLite with built-in sqlite3, WAL mode, foreign keys on. schema.sql plus simple numbered migrations tracked in a schema_version table.
- Uploaded files stored on disk as data/files/<first 2 chars>/<uuid>. The original filename lives only in the DB. Folders are DB rows only, not real directories.
- Auth: one password, Argon2id hash (argon2-cffi) stored in a settings table, set via a CLI command. Signed session cookie (Starlette SessionMiddleware). Login required everywhere except /login, /static, /healthz.
- The app listens on plain HTTP bound to 127.0.0.1:8000 on the host. HTTPS comes from `tailscale serve` on the office computer.
- Dependencies: fastapi, uvicorn, jinja2, python-multipart, argon2-cffi, itsdangerous, pillow. Dev: pytest, httpx. Justify anything else.

The office computer runs [Windows 11 / macOS / Ubuntu Linux].

Write:
1. Folder structure, one line per file describing its job.
2. SQLite schema: settings, folders, files, notes, clips, links. Columns, types, indexes. `pinned` as a column on each item table. Timestamps as ISO-8601 UTC text. clips has a `hidden` flag.
3. Route table: method, path, purpose, request and response shape. HTML pages and /api endpoints separately.
4. .env settings with defaults: VAULT_DATA_DIR, SESSION_SECRET, MAX_UPLOAD_SIZE_MB, VAULT_COOKIE_SECURE, VAULT_ALLOWED_ORIGINS, SESSION_DAYS, BACKUP_KEEP.
5. Security checklist, each item mapped to where it lives in the code.
6. Testing approach: pytest fixtures for a temp data dir, an app client, and a logged-in client.
7. Gotchas we must handle, and how:
   - Clipboard API only works over HTTPS → tailscale serve + textarea fallback
   - iPhone Safari requires the clipboard write inside the tap handler, so copy text must already be in the page (no fetching it first)
   - iPhone photos need EXIF rotation applied to thumbnails
   - HEIC images may not generate thumbnails → show a file icon, don't crash
   - Video playback and seeking on iPhone needs HTTP Range (206) responses
   - Large uploads must stream to disk, never be read fully into memory
   - Uploaded HTML, SVG and other active content must never be shown inline (same-origin XSS) → force download
   - Copying a live SQLite file can corrupt the backup → use the SQLite backup API
8. A checklist in docs/PROGRESS.md for these stages: S1 skeleton, S2 login, S3 phone access via Tailscale, S4 clipboard, S5 notes + links, S6 files core, S7 folders, S8 previews + photos, S9 home + favorites + search, S10 backup + README, S11 hardening.
```

---

# PART B: Build Stages

Every stage prompt follows the same shape: goal, what to build, what NOT to build, tests, and "done when" checks you run yourself.

## S1: Walking skeleton

```text
Read docs/RULES.md, docs/TECH_PLAN.md and docs/PROGRESS.md.

Stage 1: walking skeleton. Goal: the real app structure runs in Docker with the real layout and navigation, but no features.

Build:
- Folder structure from TECH_PLAN.md (only files this stage needs).
- requirements.txt with pinned versions.
- app/config.py: reads settings from environment / .env with safe defaults. The app refuses to start with a clear message if SESSION_SECRET is missing, too short, or still the example value.
- app/db.py: creates data folders, opens SQLite with WAL + foreign keys, runs schema/migrations on startup (safe to run repeatedly).
- Base Jinja2 layout reusing the CSS and components from /mockups: header, desktop sidebar, mobile bottom tab bar, toast area. Placeholder pages for Home, Files, Photos, Notes, Clipboard, Links, Favorites.
- GET /healthz → {"ok": true}.
- Security headers middleware: X-Content-Type-Options nosniff, Referrer-Policy same-origin, X-Frame-Options DENY, a Content-Security-Policy allowing only same-origin scripts, styles and images.
- Friendly 404 and 500 pages with no stack traces.
- Dockerfile: python:3.12-slim, non-root user, only runtime dependencies.
- docker-compose.yml: restart: unless-stopped, ./data mounted to /data, port published as "127.0.0.1:8000:8000", a healthcheck using /healthz.
- .env.example with comments, .gitignore (data/, backups/, .env, __pycache__).
- A one-liner in the README for generating SESSION_SECRET.
- tests/conftest.py with temp data dir and client fixtures, and a test for /healthz.

Do NOT build: login, any real feature.

Done when:
- `pytest` passes
- `docker compose up -d --build` works and http://localhost:8000 shows the layout
- ./data appears on the host and survives `docker compose down` then `up -d`
- the layout looks right at 375px in browser dev tools, in light and dark mode

Update docs/PROGRESS.md and give me the exact verification commands for [my OS].
```

---

## S2: Login

```text
Read docs/RULES.md, docs/TECH_PLAN.md and docs/PROGRESS.md.

Stage 2: login. Goal: nothing in the app is reachable without the password.

Build:
- CLI command to set or change the password: `docker compose run --rm vault python -m app.cli set-password`. Prompts twice with hidden input, requires at least 12 characters, stores an Argon2id hash (argon2-cffi defaults) in the settings table. The plaintext never touches disk, logs or .env.
- Changing the password logs out all existing sessions (store a session version in settings, check it on each request).
- If no password is set yet, the login page shows the command to run instead of a form.
- Login page from the mockup. POST /login, POST /logout.
- Session: signed cookie, HttpOnly, SameSite=Lax, Secure when VAULT_COOKIE_SECURE=true, lasts SESSION_DAYS (default 30).
- Auth middleware that protects EVERYTHING by default, with an allowlist of /login, /static, /healthz. Browser page requests redirect to /login?next=...; /api requests get 401 JSON. `next` must be a relative path (no open redirects).
- Failed login limit: in memory, per client IP. After 5 failures, block that IP for 60 seconds, doubling up to 15 minutes. Same error message for every failure.
- CSRF protection the simple way: for POST/PUT/PATCH/DELETE, reject requests whose Origin (or Referer if Origin is missing) doesn't match the request host or VAULT_ALLOWED_ORIGINS.
- Logout button in the sidebar and Settings.

Do NOT build: multiple users, password reset emails, 2FA, remember-me checkboxes.

Tests:
- correct password logs in; wrong password fails
- protected page redirects when logged out; protected /api returns 401
- the 6th failed attempt is blocked
- logout clears access
- changing the password invalidates an old session
- a POST with a foreign Origin is rejected
- `next=https://evil.example` is ignored

Done when: tests pass, and in Docker I can set a password, log in, refresh, log out, and get locked out briefly after 5 wrong tries.

Update docs/PROGRESS.md.
```

---

## S3: Reach it from your phone (HTTPS over Tailscale)

This stage is mostly you doing things. The prompt gets you a clear guide and a diagnostic page.

```text
Read docs/RULES.md and docs/PROGRESS.md.

Stage 3: private access from my phone over Tailscale with HTTPS.

My office computer runs [Windows 11 / macOS / Ubuntu Linux]. My devices: [iPhone / Android phone, laptop].

1. Write docs/TAILSCALE.md for a non-developer, step by step:
   - Install Tailscale on the office computer and sign in; set it to start automatically on boot.
   - Install Tailscale on phone and laptop with the same account.
   - In the Tailscale admin console: enable MagicDNS and HTTPS certificates. Optionally rename the office machine to "office-vault".
   - On the office computer run the command that serves the app over HTTPS in the background (e.g. `tailscale serve --bg 8000`). Check current Tailscale documentation for the exact syntax and mention how to see, reset and turn it off.
   - The resulting address looks like https://office-vault.[tailnet-name].ts.net
   - Set VAULT_COOKIE_SECURE=true and VAULT_ALLOWED_ORIGINS to that address in .env, then restart the app.
   - Explain in two sentences why no router ports or port forwarding are needed, and that the app itself is only bound to 127.0.0.1.
   - Make sure Docker is set to start on boot, so the vault comes back after a restart.

2. Add a Settings/About page (logged in only) showing: app version, connection is HTTPS yes/no, clipboard access available yes/no (window.isSecureContext), storage used, number of files/notes/clips/links, and a Logout button.

Do NOT: expose anything publicly, use Tailscale Funnel, or add a reverse proxy.

Done when: on my phone, with Wi-Fi off (mobile data only), I can open the https://...ts.net address, log in, and Settings shows HTTPS ✓ and Clipboard ✓.

Update docs/PROGRESS.md.
```

---

## S4: Clipboard (the pattern-setter)

This is the first real feature, and it deliberately sets the code pattern that Notes, Links and Files will copy.

```text
Read docs/RULES.md, docs/TECH_PLAN.md, docs/DESIGN.md and docs/PROGRESS.md.

Stage 4: Clipboard. Goal: I can save frequently used text and copy it on my phone in one tap. This is also the reference implementation for every later feature, so keep it clean and small.

Build:
- clips table per TECH_PLAN (title, content, hidden, pinned, created_at, updated_at).
- A small data-access module for clips (plain SQL functions), a router for the page, a router for /api/clips.
- API: list (with ?q= search on title and content), create, update, delete, toggle pin. Validate lengths (title ≤ 200, content ≤ 100 KB).
- Clipboard page from the mockup: search box at the top, pinned first then most recently updated, each item shows title, content preview (or •••••• if hidden), a large COPY button, and a ⋯ menu (edit, pin/unpin, delete).
- Quick add: title + content, save in one step. Editing works in a bottom sheet on mobile, a modal on desktop.
- Delete asks for confirmation.
- static/js/copy.js: one reusable helper used by any element with a data-copy attribute.
  - Use navigator.clipboard.writeText when window.isSecureContext, otherwise a hidden-textarea fallback that also works on iPhone Safari.
  - The copy must happen synchronously inside the tap handler. The text comes from the page (a data attribute or hidden element), never fetched first.
  - Button shows "Copied ✓" for 1.5 seconds; on failure show "Couldn't copy, press and hold to select".
- Hidden clips: content is still in the page for copying but visually masked, with a reveal toggle.
- Write the pattern down: add a short "How a feature is structured" section to docs/RULES.md (files involved, naming, how JS calls the API, how errors show as toasts).

Do NOT build: categories, tags, history of copies, sync to the device clipboard automatically.

Tests: create, list, search, update, pin, delete; validation errors; logged-out access returns 401.

Done when: on my phone over the ts.net address I can add "Wi-Fi Password", tap COPY, paste it into another app, and see Copied ✓. Hidden items work.

Update docs/PROGRESS.md.
```

---

## S5: Notes and Links

```text
Read docs/RULES.md (especially "How a feature is structured"), docs/TECH_PLAN.md and docs/PROGRESS.md.

Stage 5: Notes and Links. Follow exactly the same structure as Clipboard. Reuse components; don't invent new patterns.

NOTES
- notes table: title, body, pinned, created_at, updated_at.
- Notes list: search box, pinned first then recently updated, each row shows title (or first line of body if untitled), a one-line preview, relative date.
- "New note" creates the note and opens the editor immediately with the cursor in the body. One tap to start writing.
- Editor: title field + large plain-text textarea. Autosave 800ms after I stop typing, and also when I leave the page or switch apps (visibilitychange). Small status: "Saving…" / "Saved" / "Not saved, retrying". Empty untitled notes are discarded when I leave.
- Editor actions: copy whole note, pin, delete (confirm).
- On mobile the editor must stay usable with the keyboard open (textarea not hidden behind it).
- If the same note is edited on two devices, last save wins. That's acceptable; just don't crash.

LINKS
- links table: title, url, description, pinned, created_at.
- Only http:// and https:// URLs are accepted (reject javascript:, data:, etc.). If I type "example.com", add https:// for me.
- If title is empty, use the hostname. Do not fetch the page from the server.
- Links list: title, hostname, description; tapping opens in a new tab with rel="noopener noreferrer". Row actions: copy URL, edit, pin, delete.

Do NOT build: Markdown rendering, rich text, tags, link previews or favicons fetched from the internet.

Tests: note CRUD, autosave endpoint updates updated_at, search; link CRUD, javascript: URL rejected, missing scheme fixed; 401 when logged out.

Done when: on my phone I can create a note, type, lock the phone mid-sentence, reopen and find the text saved. I can save and open a link.

Update docs/PROGRESS.md.
```

---

## S6: Files core (upload, download, rename, delete)

```text
Read docs/RULES.md, docs/TECH_PLAN.md and docs/PROGRESS.md.

Stage 6: file uploads. Goal: I can send any file from phone or computer into the vault and get it back. This is the most security-sensitive stage, so be careful and keep it simple.

Storage:
- files table per TECH_PLAN (id uuid, folder_id nullable for now, original_name, size, mime, pinned, created_at, updated_at).
- Stored on disk as data/files/<first 2 chars of id>/<id>. The stored path is built ONLY from the generated id. Before any read or delete, resolve the path and assert it is inside data/files.
- Display names: take only the last path segment (split on both / and \), remove control characters and null bytes, trim spaces and dots at the ends, max 255 chars, fall back to "unnamed". It's display text only.
- MIME type from the extension (mimetypes), not from what the browser claims.

Upload:
- POST /api/files accepts one or more files.
- Stream each file to a temp file in data/tmp in 1 MB chunks, enforce MAX_UPLOAD_SIZE_MB while streaming (stop and delete the temp file when exceeded), then move it into place atomically and insert the DB row. If anything fails, no orphan temp files or half DB rows.
- Return per-file results so one bad file doesn't fail the whole batch.

Upload UI:
- The Upload button (reachable from every page) opens a normal <input type="file" multiple> with no accept restriction, so iPhone/Android offer camera, photo library and files.
- Drag and drop anywhere on the page on desktop, with a clear drop overlay.
- Upload panel: one row per file with name, size, progress bar (use XMLHttpRequest upload progress; fetch can't report upload progress), done/error state, and a cancel button. Upload at most 2 files at a time.
- Warn before leaving the page while uploads are in progress.
- New files appear in the list without a page reload.

Files page (no folders yet):
- List: type icon, name, size (human readable), date, pin indicator. Newest first.
- Row actions via ⋯: download, rename, copy filename, pin, delete (confirm).

Serving files:
- GET /api/files/{id}/download → always Content-Disposition: attachment, with a correct UTF-8 filename (filename* form) so names like "रसीद.pdf" work.
- GET /api/files/{id}/view → inline ONLY for a safe allowlist: common images (not SVG), PDF, MP4/WebM/MOV video, common audio, plain text served as text/plain. Everything else (including HTML, SVG, XML, JS) is forced to download. Add a restrictive CSP (sandbox) header on these responses.
- Must support HTTP Range requests (206) so video can play and seek on iPhone. Verify it; implement if the framework version doesn't.

Delete: remove DB row and disk file. If the disk file is already missing, still delete the row and log a warning without the filename content.

Do NOT build: folders, thumbnails, previews, chunked/resumable uploads, deduplication.

Tests:
- upload then download returns identical bytes
- multiple files in one request
- names like "../../etc/passwd", "..\\..\\boot.ini", "a\x00b.txt", "   ", and a 300-char name are stored safely and displayed sanitized
- stored file path is always inside data/files
- size limit rejects and leaves no temp file behind
- rename, pin, delete (row and disk file gone)
- an uploaded .html file is served as attachment from /view
- Range request returns 206 with correct bytes
- all endpoints 401 when logged out

Done when: from my phone I can take a photo, upload it, see progress, and see it listed; from my laptop I can drag in 5 files including a 500 MB video [adjust size to your needs] and download them back. Rename and delete work.

Update docs/PROGRESS.md.
```

---

## S7: Folders, move, sort

```text
Read docs/RULES.md, docs/TECH_PLAN.md and docs/PROGRESS.md.

Stage 7: folders. Folders exist only in the database (parent_id tree). Moving or renaming never touches files on disk.

Build:
- folders table: id, parent_id (null = root), name, created_at. Folder names sanitized like filenames, unique within the same parent (case-insensitive).
- Files page shows the current folder: breadcrumb, subfolders first, then files. The folder is in the URL (/files?folder=<id>) so back/forward and refresh work.
- Create folder, rename folder.
- Delete folder: if not empty, the confirmation says exactly what will be deleted ("3 folders and 42 files"). Deletes DB rows and disk files.
- Move: for one file or folder, and for multiple selected items. A folder picker dialog to choose the destination. Moving a folder into itself or its own subfolder is rejected.
- Selection: a "Select" button enters selection mode (checkboxes). Works well on touch; no long-press tricks required.
- Uploads go into the folder I'm currently viewing.
- Sort by name, date, size, ascending/descending, stored in the URL. A filter box that narrows the current folder's list.

Do NOT build: shared folders, folder colours, drag-to-move on mobile (drag-to-move on desktop is optional, only if simple).

Tests: create, rename, duplicate name rejected, nested move, move-into-own-child rejected, recursive delete removes disk files, upload into folder, sort order.

Done when: I can create "Documents/Bills/2026", upload into it from my phone, select 5 files on my laptop and move them, and the breadcrumb and back button behave.

Update docs/PROGRESS.md.
```

---

## S8: Previews, thumbnails, Photos

```text
Read docs/RULES.md, docs/TECH_PLAN.md, docs/DESIGN.md and docs/PROGRESS.md.

Stage 8: previews and the Photos gallery.

Thumbnails:
- Generated with Pillow on first request, cached as data/thumbs/<id>.webp (about 400px on the long side). Deleting a file deletes its thumbnail.
- Apply EXIF orientation (ImageOps.exif_transpose) so phone photos aren't sideways.
- Protect against huge "decompression bomb" images with a sensible pixel limit.
- If a thumbnail can't be made (HEIC, corrupt, unsupported), return nothing and the UI shows the file-type icon. Never a 500.
- Thumbnails are behind login like everything else, with a private cache header.

Preview page (/files/<id>):
- Image: full image, fits the screen.
- PDF: embedded viewer on desktop; on phones show a large "Open PDF" button (opens the /view URL in a new tab so the phone's native viewer handles it).
- Video/audio: <video controls playsinline preload="metadata"> / <audio controls>.
- Text files (known text extensions, under 1 MB): shown escaped in a scrollable block with a COPY button.
- Anything else: name, type, size, dates, and a Download button.
- Every preview has: download, rename, pin, move, delete, copy filename.

Photos page:
- All images (and a toggle to include videos) across all folders, newest first.
- Grid: 3 columns on phone, 4–6 on larger screens, square tiles, loading="lazy", loads 60 at a time as I scroll.
- Tapping opens a full-screen viewer: swipe left/right on touch, arrow keys on desktop, Esc or ✕ to close, and the browser back button closes the viewer instead of leaving the page.
- Viewer actions: download, pin, rename, delete (then shows the next photo), and "Copy link", which copies the internal https://...ts.net/files/<id> address. It only works for someone logged in to my vault; say that in the toast.

Do NOT build: albums, face/object detection, editing, EXIF maps, public share links.

Tests: thumbnail generated for a PNG and a rotated JPEG (orientation applied), no crash on a fake .heic, thumbnail deleted with its file, preview page per type returns 200, Photos pagination.

Done when: on my phone Photos shows a fast grid of my uploads, the viewer swipes smoothly, an iPhone photo isn't rotated, a video plays and seeks, and a PDF opens.

Update docs/PROGRESS.md.
```

---

## S9: Home dashboard, Favorites, universal search

```text
Read docs/RULES.md, docs/TECH_PLAN.md, docs/DESIGN.md and docs/PROGRESS.md.

Stage 9: bring it together. The Home page must answer in one glance: what did I recently upload, what did I pin, what can I quickly copy.

Home:
- Pinned section: mixed items, each with its main action inline. Clip → COPY. File → View. Note → Open. Link → Open. Limit 8 with "See all".
- Recent files: last 8, with thumbnails where available.
- Recent notes: last 5.
- Quick-access tiles for sections (compact on mobile, don't push Pinned below the fold).
- Helpful empty states for a brand-new vault ("Upload your first file", "Save a text you copy often").

Favorites page: all pinned items grouped by type, same inline actions as Home.

Search:
- GET /api/search?q= searches folder names, file names, note titles and bodies, clip titles and content, link titles, URLs and descriptions.
- Case-insensitive LIKE with % and _ escaped properly, up to 20 results per type, results grouped by type. Hidden clips match but their content stays masked in results.
- Header search: on desktop a search field (press "/" to focus); on mobile a search icon that opens a full-screen search with live results as I type (250ms debounce). Enter goes to a /search?q= page.
- Each result has its main action (COPY for clips).
- Note bodies show a short snippet around the match.

Do NOT build: SQLite FTS (note it in BACKLOG as an upgrade if search ever gets slow), search filters, saved searches.

Tests: search finds each item type, % and _ in queries don't act as wildcards, results require login, pinned items appear on Home and Favorites.

Done when: on my phone, Home shows my pinned Wi-Fi password with a working COPY button, and searching "bill" finds the folder, the PDF and the note.

Update docs/PROGRESS.md.
```

---

## S10: Backup, restore, README

```text
Read docs/RULES.md, docs/TECH_PLAN.md and docs/PROGRESS.md. My office computer runs [Windows 11 / macOS / Ubuntu Linux].

Stage 10: backups and documentation.

Backup:
- app/backup.py, run inside the container: `docker compose exec vault python -m app.backup`
- Copies the database with the SQLite online backup API (safe while the app is running), runs PRAGMA integrity_check on the copy, then creates backups/vault-YYYY-MM-DD_HHMM.tar.gz containing the database copy and data/files. Thumbnails and temp files are excluded (they can be regenerated).
- ./backups is a separate mounted folder, not inside ./data.
- Keeps the newest BACKUP_KEEP archives (default 14) and deletes older ones.
- Prints the archive path and size. Exit code non-zero on any failure.
- backup.sh wrapper for macOS/Linux [and backup.ps1 for Windows if my OS is Windows].

Restore:
- `docker compose down`, then `docker compose run --rm vault python -m app.restore backups/<file>.tar.gz`
- Validates the archive first. Never deletes current data: moves it to data.before-restore-<timestamp>/ and then extracts.
- Clear success message with the next command to start the app.

Scheduling: instructions for a daily automatic backup using [cron / launchd / Windows Task Scheduler]. Strongly recommend copying the backups folder to an external drive or second computer weekly, because a backup on the same disk doesn't survive a disk failure.

README.md written for a non-developer, following the sections in docs/SPEC.md:
What this is · Install Docker and Tailscale · First-time setup (copy .env.example, generate SESSION_SECRET, set password) · Start · Access from phone (link to docs/TAILSCALE.md) · Change password · Update to a new version (git pull, docker compose up -d --build) · Backup · Restore · Troubleshooting · Project structure · Why these technologies (a few sentences).

Troubleshooting must cover at least: COPY button doesn't work (not on HTTPS), can't reach the vault from phone (Tailscale off on one device), login keeps failing / locked out, upload fails for big files (MAX_UPLOAD_SIZE_MB), app not running after reboot (Docker not starting on boot), "database is locked", disk full, forgot password (run set-password again).

Tests: backup then restore into a temp folder round-trips files and database content; old backups are pruned.

Done when: I run a backup, delete a test note, restore, and the note is back.

Update docs/PROGRESS.md.
```

---

## S11: Hardening and final checks

```text
Read all files in docs/ and review the whole codebase.

Stage 11: final hardening. Don't add features. Work through this list, fix real problems, and report what you found.

1. Security review against docs/SPEC.md section 13 and the checklist in TECH_PLAN.md. For each item: where it's implemented, and whether a test covers it. Specifically try to find: any route reachable without login, any path built from user input, any user content rendered without escaping, any uploaded type that can render as HTML, passwords or note/clip content appearing in logs or error pages.
2. Reliability: app starts cleanly on an empty data folder; restart during an upload leaves no broken state; tmp folder cleaned on startup; database migrations are safe to re-run.
3. Mobile QA at 375px and 768px, light and dark: tap targets ≥ 44px, inputs ≥ 16px, nothing hidden behind the iPhone home bar or keyboard, long filenames truncate nicely, no horizontal scrolling anywhere.
4. Performance: Home and Files load fast with 2,000 files and 500 notes. Write a small seed script (scripts/seed_demo.py, uses a separate data dir) to test this; add indexes if needed.
5. Fresh install test: clone the repo into a temp folder, follow the README exactly from scratch, and fix anything in the README that was wrong or missing.
6. Run the full test suite and `docker compose up -d --build`, check /healthz, log in, upload and download one file.

Output: a short report (found / fixed / left for BACKLOG), final project structure, and the final PROGRESS.md.
```

---

# PART C: Utility Prompts

## Session starter (paste first in every new session)

```text
We're building my Personal Vault app. Before anything else, read docs/RULES.md and docs/PROGRESS.md, and skim docs/TECH_PLAN.md.

Then tell me in 5 lines or fewer: what's done, which stage is next, and anything in the code that looks broken or inconsistent. Don't write code until I send the stage prompt.
```

## Verify a stage before committing

```text
Before I commit this stage:
1. Run the full test suite and show me the summary.
2. Rebuild and start with docker compose; confirm /healthz and that the app logs show no errors.
3. List every "Done when" check from this stage and whether you verified it or I need to check it on my phone.
4. Check you didn't break earlier stages (log in, copy a clip, open a note, download a file — whichever exist so far).
5. Show me `git status` and suggest a commit message.
```

## Report a bug

```text
Bug:
- What I did: [steps]
- What I expected: [...]
- What happened: [...]
- Device/browser: [e.g. iPhone 14, Safari] over [ts.net HTTPS / localhost]
- Error shown or logs: [paste `docker compose logs --tail=50 vault` if relevant]

First explain the likely cause in 2–3 sentences. Then fix it with the smallest change, add a test that would have caught it, and run the tests.
```

## When the code gets too complicated

```text
This feels over-engineered. Review [the files / this stage] and find anything we don't need for a single-user personal tool: extra abstractions, unused options, duplicated helpers, dependencies we could drop, configuration nobody will change. Propose a simpler version, list what gets removed, and only apply it after I say yes. Behaviour and tests must stay the same.
```

## Add a feature later

```text
Read docs/RULES.md, docs/TECH_PLAN.md and docs/PROGRESS.md.

I want to add: [feature]. Why: [what annoys me today].

First give me a short plan: the smallest version that solves this, files touched, any database change (as a new numbered migration), any new dependency (justify it), and what you'll NOT include. Wait for my OK, then build it following "How a feature is structured", with tests and a PROGRESS.md update.
```

---

# PART D: Backlog for v2 (only after you've used v1 for a few weeks)

Ideas worth doing once the basics feel solid, roughly in order of everyday value:

- **Install as an app** (PWA manifest + icon) so the vault opens from your home screen without browser bars.
- **Share into the vault from other apps.** On Android, a Web Share Target lets you pick "Vault" from the share sheet. iPhone doesn't support that for web apps, but an iOS Shortcut can upload to the API.
- **Trash with 30-day restore** instead of immediate delete.
- **Paste to upload**: paste a screenshot or text on desktop and it becomes a file or clip.
- **Markdown preview** for notes (needs a safe renderer, so a small dependency decision).
- **HEIC thumbnails** via pillow-heif.
- **SQLite FTS5** search if LIKE search ever feels slow.
- **Automatic off-machine backup copy** to an external drive or another computer on the tailnet.
