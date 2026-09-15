# Technical plan

Written in D5. Read together with `CLAUDE.md` (rules), `docs/DESIGN.md` (what it looks like)
and `docs/PROGRESS.md` (where we are). Where the playbook's stage prompts and `DESIGN.md`
disagree, `DESIGN.md` wins — it is the reviewed spec. Every such case is listed in §9 so a
stage never has to guess.

Server: Ubuntu 26.04 office computer, Docker Compose, reached over `tailscale serve` HTTPS.
Devices: Android phone, laptop.

---

## 0. Shape of the app in one paragraph

One FastAPI process. Pages are Jinja2 templates rendered on the server with real data. Every
change (create, update, delete, favorite, upload, move) is a JSON call under `/api/`, made
by one vanilla `static/js/app.js`. After a change, the JS swaps in a fresh copy of the page's
content from the same URL with `?partial=1` — so there is exactly one template per list and
no HTML is ever built in JavaScript. SQLite in one file. Uploaded bytes on disk under
generated ids. No background workers, no queue, no cache server.

---

## 1. Folder structure

```text
personal-vault/
├── CLAUDE.md                  rules for every session
├── README.md                  for a non-developer: install, start, access, backup, restore (S10)
├── Dockerfile                 python:3.12-slim, non-root user, runtime deps only
├── docker-compose.yml         one service "vault"; ./data and ./backups mounted; 127.0.0.1:8000
├── requirements.txt           pinned runtime dependencies
├── requirements-dev.txt       -r requirements.txt + pytest, httpx
├── .env.example               every setting from §4 with a comment
├── .gitignore                 data/, backups/, .env, __pycache__/, .pytest_cache/
├── backup.sh                  `docker compose exec vault python -m app.backup` wrapper
├── app/
│   ├── __init__.py
│   ├── main.py                create_app(settings): middleware, routers, /static mount, error pages, /healthz
│   ├── config.py              Settings dataclass read from env; refuses to start on a bad SESSION_SECRET
│   ├── db.py                  connect (WAL, foreign keys), run migrations, now(), transaction helper
│   ├── migrations/
│   │   └── 001_initial.sql    the whole v1 schema (§2); later changes are 002_*.sql, 003_*.sql …
│   ├── security.py            security headers, auth gate, Origin check, login rate limiter
│   ├── auth.py                password hash/verify, session version, /login, /logout, /api/password
│   ├── cli.py                 `python -m app.cli set-password`
│   ├── web.py                 Jinja env, filters (size, relative date, name split), render(partial-aware)
│   ├── storage.py             id → path, safe display name, stream-to-tmp, move into place, delete, MIME, inline allowlist
│   ├── thumbs.py              Pillow thumbnails with EXIF rotation and a pixel limit
│   ├── clips.py               clips: SQL functions + page routes + /api/clips   (S4 — the reference feature)
│   ├── notes.py               notes: same shape                                   (S5)
│   ├── links.py               links: same shape, URL normalisation                (S5)
│   ├── files.py               files + folders: SQL, /files pages, /api/files, /api/folders, bulk move/delete (S6, S7)
│   ├── photos.py              /photos grid and viewer (a view over files)          (S8)
│   ├── home.py                /, /favorites, /search, /api/search, /settings       (S9, S3)
│   ├── backup.py              `python -m app.backup`                              (S10)
│   ├── restore.py             `python -m app.restore <archive>`                   (S10)
│   └── templates/
│       ├── base.html          shell: sidebar, top bar, tab bar, toast region, delete modal
│       ├── partial.html       bare wrapper used when ?partial=1
│       ├── macros.html        row macros (file, folder, note, clip, clip_compact, link), sheets, empty state
│       ├── login.html
│       ├── home.html  favorites.html  search.html  settings.html
│       ├── files.html  preview.html  photos.html  viewer.html
│       ├── notes.html  editor.html    (editor.html serves notes AND clips)
│       ├── clipboard.html  links.html  link_form.html
│       └── error.html         404 / 500, no details
├── static/                    served at /static (already exists from D2/D3)
│   ├── css/tokens.css  css/app.css
│   ├── js/app.js              all behaviour, delegated data-* handlers (§6 of this doc lists additions)
│   └── icons/*.svg  icons/LICENSE
├── mockups/                   D3 reference pages; not served by the app
├── scripts/
│   └── seed_demo.py           S11: fills a separate data dir with 2,000 files / 500 notes
├── tests/
│   ├── conftest.py            fixtures (§6)
│   ├── test_health.py  test_auth.py  test_security.py
│   ├── test_clips.py  test_notes.py  test_links.py
│   ├── test_files.py  test_folders.py  test_thumbs.py  test_photos.py
│   ├── test_search.py  test_home.py  test_backup.py
└── docs/                      SPEC, PLAYBOOK, DESIGN, TECH_PLAN, PROGRESS, BACKLOG, TAILSCALE (S3)
```

Why one module per feature instead of `app/clips/{repo,pages,api}.py`: each feature is
~150–300 lines; three files each would triple the file count for nothing. Inside a module the
order is always the same — **SQL functions, then page routes, then `/api` routes** — and
that order is the "How a feature is structured" section S4 writes into `CLAUDE.md`. A module
that passes ~500 lines (only `files.py` might) splits into `files.py` + `folders.py`.

Why `static/` stays at the repo root, not `app/static/`: the mockups link to `../static/`,
and they stay the visual reference through S11.

---

## 2. SQLite schema

Rules: `STRICT` tables. Timestamps are ISO-8601 UTC text, always the same fixed format
`2026-09-15T10:32:07Z`, produced only by `db.now()` — so text order is time order. Booleans
are `INTEGER` 0/1 with a CHECK. Every list query ends with `, id DESC` so ties are stable.

The column is **`favorite`**, not `pinned` (see §9) — the UI says Favorite everywhere since D4.

```sql
-- 001_initial.sql

CREATE TABLE schema_version (
  version    INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
) STRICT;

-- Key/value. Keys used: password_hash, session_version, files_sort (root folder's sort).
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) STRICT;

CREATE TABLE folders (
  id         INTEGER PRIMARY KEY,
  parent_id  INTEGER REFERENCES folders(id) ON DELETE CASCADE,   -- NULL = root
  name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255),
  sort       TEXT NOT NULL DEFAULT 'name' CHECK (sort IN ('name','-name','date','-date','size','-size','type','-type')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
-- Unique name per parent, case-insensitive. IFNULL because NULLs never collide in a UNIQUE index.
CREATE UNIQUE INDEX folders_parent_name ON folders (IFNULL(parent_id, 0), name COLLATE NOCASE);

CREATE TABLE files (
  id            TEXT PRIMARY KEY CHECK (length(id) = 32),          -- uuid4().hex, also the disk name
  folder_id     INTEGER REFERENCES folders(id) ON DELETE CASCADE,  -- NULL = root
  name          TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255),  -- display text only
  size          INTEGER NOT NULL CHECK (size >= 0),
  mime          TEXT NOT NULL,                                     -- from the extension, never the browser
  kind          TEXT NOT NULL CHECK (kind IN ('image','video','audio','pdf','text','other')),
  favorite      INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at    TEXT NOT NULL,                                     -- upload time
  updated_at    TEXT NOT NULL
) STRICT;
CREATE INDEX files_folder   ON files (folder_id, name COLLATE NOCASE);
CREATE INDEX files_recent   ON files (created_at DESC);
CREATE INDEX files_photos   ON files (kind, created_at DESC);        -- Photos grid
CREATE INDEX files_favorite ON files (favorite) WHERE favorite = 1;

CREATE TABLE notes (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT '' CHECK (length(title) <= 200),
  body       TEXT NOT NULL DEFAULT '' CHECK (length(body) <= 1000000),
  favorite   INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
CREATE INDEX notes_list ON notes (favorite DESC, updated_at DESC);

CREATE TABLE clips (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT '' CHECK (length(title) <= 200),
  content    TEXT NOT NULL DEFAULT '' CHECK (length(content) <= 100000),
  hidden     INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
  favorite   INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
CREATE INDEX clips_list ON clips (favorite DESC, updated_at DESC);

CREATE TABLE links (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  url         TEXT NOT NULL CHECK (length(url) <= 2000 AND (url LIKE 'http://%' OR url LIKE 'https://%')),
  description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 1000),
  favorite    INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;
CREATE INDEX links_list ON links (favorite DESC, created_at DESC);
```

Notes on the schema:

- **`kind`** is computed once at upload from the extension, so Photos, the preview page and
  the icon choice never re-guess. `mime` is what `Content-Type` is served as.
- **Deleting a folder** cascades to sub-folders and file rows in the DB, but the disk files
  must go too: `files.delete_folder()` first collects every file id in the subtree (one
  recursive CTE), deletes the rows in a transaction, then removes disk files and thumbnails.
  A crash between the two leaves orphan bytes, never a row pointing at nothing; S11's
  startup check lists orphans (§7).
- **Lengths are also CHECKed in SQL**, as a last line behind the API validation. The API
  returns a friendly 422 first; the CHECK only catches a bug.
- **`clips.hidden` content is never matched by search** (DESIGN §3.12), so search queries
  use `CASE WHEN hidden THEN '' ELSE content END`.
- **Migrations:** `db.migrate()` runs at startup: reads `MAX(version)`, applies each
  `NNN_*.sql` above it inside its own transaction, inserts the version row. Safe to run
  repeatedly. No down-migrations — restore from backup instead.

---

## 3. Routes

Every route requires login except the three marked **public**. Every non-GET request must
pass the Origin check (§5). Errors from `/api` are always `{"error": "<human sentence>"}`
with a 4xx/5xx status — the JS shows the sentence as a toast, never a status code.

### 3.1 HTML pages

Any page marked *partial* also answers `?partial=1` with just its `<main>` content (no shell),
used by the JS to refresh after a change, load more photos, and show live search.

| Method | Path | Purpose | Stage |
|---|---|---|---|
| GET | `/healthz` | **public** `{"ok": true}`; also checks the DB answers `SELECT 1` | S1 |
| GET | `/static/…` | **public** CSS, JS, icons | S1 |
| GET | `/login` | **public** form; if no password is set, shows the `set-password` command instead | S2 |
| POST | `/login` | **public** form `password`, `next` → 303 to `next` (relative only) or `/`; wrong → 200 form + same error text; locked → 429 form | S2 |
| POST | `/logout` | clear session → 303 `/login` | S2 |
| GET | `/` | Home: Favorites (max 6) + Recent (max 10, mixed), *partial* | S9 |
| GET | `/files?folder=<id>&sort=<s>` | folder contents, folders first; `sort` saved to the folder when given, *partial* | S6/S7 |
| GET | `/files/{id}` | preview page by `kind` | S8 |
| GET | `/photos?before=<created_at>,<id>` | grid, 60 per page, month headings, *partial* (next page) | S8 |
| GET | `/photos/{id}` | full-screen viewer: this photo plus up to 10 neighbours each side | S8 |
| GET | `/notes` | list, *partial* | S5 |
| POST | `/notes/new` | create empty note → 303 `/notes/{id}` (a form button, works without JS) | S5 |
| GET | `/notes/{id}` | editor | S5 |
| GET | `/clipboard` | list, *partial* | S4 |
| POST | `/clipboard/new` | create empty clip → 303 `/clipboard/{id}` | S4 |
| GET | `/clipboard/{id}` | editor (same template as notes, plus a Hidden switch) | S4 |
| GET | `/links` | list, *partial* | S5 |
| GET | `/links/new`, `/links/{id}/edit` | link form page (URL, title, description) | S5 |
| GET | `/favorites?type=<t>` | all favorites, type chips, *partial* | S9 |
| GET | `/search?q=<q>&type=<t>&in=<section>` | results grouped by type, *partial* (live search) | S9 |
| GET | `/settings` | counts, storage, version, last backup, HTTPS ✓ / Clipboard ✓ (checked in JS), change password, log out | S3 |

Empty editors are discarded: leaving a note or clip with no title and no body/content sends
`DELETE` from the editor's `pagehide` handler (`navigator.sendBeacon` cannot send DELETE, so
it is `fetch(..., {keepalive: true})`).

### 3.2 JSON API

Shapes use these objects (all fields always present):

```text
Clip   {id, title, content, hidden, favorite, created_at, updated_at}
Note   {id, title, body, favorite, created_at, updated_at}
Link   {id, title, url, host, description, favorite, created_at, updated_at}
File   {id, folder_id, name, size, mime, kind, favorite, created_at, updated_at}
Folder {id, parent_id, name, sort, created_at, updated_at}
```

| Method | Path | Request | Response | Stage |
|---|---|---|---|---|
| POST | `/api/password` | `{current, new}` | 204; wrong current → 400 (counts toward lockout); logs out every other session | S2 |
| GET | `/api/clips?q=` | — | `{clips: [Clip]}` favorites first, then newest-modified | S4 |
| POST | `/api/clips` | `{title, content, hidden?}` | 201 `Clip` | S4 |
| PATCH | `/api/clips/{id}` | any of `{title, content, hidden, favorite}` | `Clip` | S4 |
| DELETE | `/api/clips/{id}` | — | 204 | S4 |
| GET | `/api/notes?q=` | — | `{notes: [Note]}` | S5 |
| POST | `/api/notes` | `{title?, body?}` | 201 `Note` | S5 |
| PATCH | `/api/notes/{id}` | any of `{title, body, favorite}` | `Note` (autosave reads `updated_at`) | S5 |
| DELETE | `/api/notes/{id}` | — | 204 | S5 |
| GET | `/api/links?q=` | — | `{links: [Link]}` | S5 |
| POST | `/api/links` | `{url, title?, description?}` | 201 `Link`; `example.com` → `https://example.com`; other schemes → 422 | S5 |
| PATCH | `/api/links/{id}` | any of `{url, title, description, favorite}` | `Link` | S5 |
| DELETE | `/api/links/{id}` | — | 204 | S5 |
| POST | `/api/files?folder_id=` | **raw file bytes** as the body; header `X-File-Name: <percent-encoded name>`; `Content-Length` required | 201 `File`; 413 `{"error": "Too large (max 2 GB)"}`; 507 `{"error": "Vault disk full"}` | S6 |
| GET | `/api/files?folder_id=&sort=` | — | `{folders: [Folder], files: [File]}` | S6 |
| PATCH | `/api/files/{id}` | any of `{name, folder_id, favorite}` | `File` | S6 |
| DELETE | `/api/files/{id}` | — | 204 | S6 |
| GET | `/api/files/{id}/download` | Range optional | bytes, always `attachment` | S6 |
| GET | `/api/files/{id}/view` | Range optional | bytes inline if on the allowlist (§5), else `attachment` | S6 |
| GET | `/api/files/{id}/thumb` | — | `image/webp`, or 404 when no thumbnail can exist | S8 |
| GET | `/api/folders` | — | `{folders: [Folder]}` whole tree, for the move picker | S7 |
| POST | `/api/folders` | `{name, parent_id}` | 201 `Folder`; duplicate name → 409 | S7 |
| PATCH | `/api/folders/{id}` | any of `{name, parent_id}` | `Folder`; into itself/descendant → 422 | S7 |
| GET | `/api/folders/{id}/summary` | — | `{folders: n, files: n, size: bytes}` for the delete confirm | S7 |
| DELETE | `/api/folders/{id}` | — | 204 (recursive) | S7 |
| POST | `/api/move` | `{files: [id], folders: [id], to: folder_id \| null}` | `{moved: n}` all-or-nothing | S7 |
| POST | `/api/delete` | `{files: [id], folders: [id]}` | `{deleted: {folders: n, files: n}}` | S7 |
| GET | `/api/search?q=&type=` | — | `{files, folders, notes, clips, links}` each ≤ 20; same function as `/search` | S9 |

Why uploads are **one file per request with a raw body** instead of one multipart request with
many files (the S6 brief): see §8 gotcha 9. The client sends two at a time, so the user still
picks many files at once, and "per-file results" come for free — each request is one result.

---

## 4. Settings (`.env`)

Read once in `config.py` into a frozen dataclass passed to `create_app()` — never read from
`os.environ` anywhere else, so tests can build an app with any settings.

| Variable | Default | Meaning |
|---|---|---|
| `SESSION_SECRET` | *(none — required)* | Signs the session cookie. ≥ 32 characters, not the `.env.example` value, or the app refuses to start and says how to generate one (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`). |
| `VAULT_DATA_DIR` | `/data` | Holds `vault.db`, `files/`, `thumbs/`, `tmp/`. Mounted from `./data`. |
| `VAULT_BACKUP_DIR` | `/backups` | Where archives go. Mounted from `./backups`, deliberately outside `./data`. |
| `MAX_UPLOAD_SIZE_MB` | `2048` | Per file. Checked against `Content-Length` before reading and again while streaming. |
| `VAULT_COOKIE_SECURE` | `false` | `true` once S3 is done and the vault is only opened over `https://…ts.net`. |
| `VAULT_ALLOWED_ORIGINS` | *(empty)* | Comma-separated extra origins for the Origin check, e.g. `https://office-vault.tail1234.ts.net`. The request's own host is always allowed. |
| `SESSION_DAYS` | `30` | Session cookie lifetime. |
| `BACKUP_KEEP` | `3` | Archives kept. Each archive is a full copy of every file — see §8 gotcha 16 for why not 14. |
| `VAULT_TIMEZONE` | `Asia/Kolkata` | Only for display ("Today, 09:15", month headings). Storage stays UTC. |
| `UID` / `GID` | `1000` | Compose only: the container runs as this user so `./data` stays owned by you. |

The SPEC's `INITIAL_PASSWORD` is deliberately **not** a setting: a password in `.env` sits in a
plaintext file forever. `set-password` prompts for it and stores only the hash.

---

## 5. Security checklist

| # | Rule | Where it lives | Test |
|---|---|---|---|
| 1 | Login required everywhere except `/login`, `/static`, `/healthz` | `security.AuthGate` middleware — an **allowlist**, so a new route is protected by default | `test_security`: walks `app.routes` and asserts every non-public route → 302 (page) / 401 (`/api`) when logged out |
| 2 | Argon2id hash only, plaintext never stored or logged | `auth.hash_password` (argon2-cffi `PasswordHasher()` defaults), `cli.set-password` uses `getpass` | hash starts `$argon2id$`; caplog contains no password |
| 3 | Session cookie: signed, HttpOnly, SameSite=Lax, Secure by setting, 30 days | Starlette `SessionMiddleware(same_site="lax", https_only=settings.cookie_secure, max_age=…)` | cookie flags asserted |
| 4 | Password change logs out other sessions | `settings.session_version` copied into the session at login, compared on every request in `AuthGate` | old client → 302 after change |
| 5 | Login rate limit | `security.LoginLimiter`: 5 failures → 60 s lock, doubling to 15 min, reset on success. **One global bucket** (§8 gotcha 11) | 6th attempt → 429 even with the right password |
| 6 | Same error text for every failed login | `auth.login_post` | wrong/locked/empty all render the same sentence |
| 7 | No open redirect | `auth.safe_next()`: must start with `/`, not `//`, no `\`, no scheme | `next=https://evil.example`, `//evil.example`, `/\evil` → `/` |
| 8 | CSRF | `security.OriginCheck`: POST/PUT/PATCH/DELETE need `Origin` (or `Referer`) equal to the request host or in `VAULT_ALLOWED_ORIGINS`; plus SameSite=Lax; `/api` writes also require `Content-Type: application/json` (uploads: `application/octet-stream`) | foreign Origin → 403; missing both → 403 |
| 9 | User names never become paths | `storage.path_for(id)`: validates `id` is 32 hex chars, builds `files/<id[:2]>/<id>`, `resolve()`s and asserts it is inside `files/` | traversal names stored safely; bad id → 404 |
| 10 | Display-name sanitising | `storage.clean_name()`: last segment after `/` or `\`, strip control chars and NUL, trim spaces/dots, ≤ 255 chars, else `unnamed` | the S6 name list |
| 11 | Active content never inline | `storage.INLINE_KINDS`: jpg, jpeg, png, gif, webp, avif, bmp; pdf; mp4, webm, mov; mp3, m4a, ogg, wav, flac; txt/md/csv/log/json **as `text/plain; charset=utf-8`**. Everything else, including html, svg, xml, js, → `attachment`. All file responses: `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox; default-src 'none'` (PDF: see §8 gotcha 7) | `.html` and `.svg` via `/view` → attachment |
| 12 | Security headers on every response | `security.HeadersMiddleware`: `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY` (SAMEORIGIN on PDF `/view`), CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` | header test on a page and an API call |
| 13 | No inline script or `style=` | templates; `test_security` greps rendered pages for `<script>` without `src` and ` style=` | yes |
| 14 | Everything escaped | Jinja autoescape on for `.html`; no `|safe` anywhere (grep in S11); JS only sets `textContent` | a note titled `<img src=x onerror=…>` renders escaped |
| 15 | Upload limits | `MAX_UPLOAD_SIZE_MB` checked on `Content-Length` and while streaming; temp file removed in `finally` | oversize → 413, `tmp/` empty |
| 16 | No secrets or content in logs or errors | uvicorn runs with `--no-access-log` (query strings carry search terms); app logs ids and sizes, never names of notes/clips, bodies, contents or passwords; 500 page is generic; `debug=False` | caplog on login + clip create + a forced 500 contains none of them |
| 17 | Hidden clip content | still in the page for COPY (§8 gotcha 2); every HTML response `Cache-Control: no-store`; excluded from search matching and snippets | search for a hidden clip's content finds nothing |
| 18 | Link URLs | `links.normalise_url()`: only http/https after adding a missing `https://`; rendered with `rel="noopener noreferrer"` | `javascript:`, `data:` → 422 |
| 19 | SQL injection | only `?` parameters; `LIKE` terms escaped with `ESCAPE '\'`; `ORDER BY` from a fixed dict, never from input | `%`, `_` literal |
| 20 | Safe deletion | row deleted in a transaction first, then disk file + thumbnail; missing disk file logs a warning with the id only | row and bytes gone |
| 21 | Not reachable from the internet | compose publishes `127.0.0.1:8000:8000` only; HTTPS via `tailscale serve` (never Funnel) | manual check in S3 |
| 22 | Pixel bombs | `thumbs.py` sets `Image.MAX_IMAGE_PIXELS = 80_000_000` and catches `DecompressionBombError` | a 20000×20000 PNG header → no thumb, no 500 |

---

## 6. Testing

`pytest` from the repo root, no Docker needed. Everything runs against a temporary data dir.

```python
# tests/conftest.py — the shape, not final code
@pytest.fixture
def settings(tmp_path):
    return Settings(session_secret="x" * 48, data_dir=tmp_path / "data",
                    backup_dir=tmp_path / "backups", max_upload_size_mb=2,
                    cookie_secure=False, allowed_origins=(), session_days=30,
                    backup_keep=3, timezone="Asia/Kolkata")

@pytest.fixture
def app(settings):
    return create_app(settings)          # creates folders, runs migrations, fresh limiter

@pytest.fixture
def client(app):                         # logged out; sends a same-origin Origin by default
    with TestClient(app, base_url="http://testserver",
                    headers={"Origin": "http://testserver"}) as c:
        yield c

PASSWORD = "correct horse battery"

@pytest.fixture
def auth_client(app, client):            # password set, logged in
    auth.set_password(app.state.db_path, PASSWORD)
    r = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303
    return client
```

- `max_upload_size_mb=2` in tests, so the size limit is tested with a 3 MB body, not 2 GB.
- The rate limiter lives on `app.state`, so each test gets a fresh one.
- Images for thumbnail tests are generated in the test with Pillow (a PNG, a JPEG with EXIF
  orientation 6, a text file named `.heic`) — no binary fixtures in git.
- One test per stage asserts **COPY data is complete**: a 50 KB clip renders its full text
  in `.clip__source` even though the preview is clipped (DESIGN §3.9).
- Each stage runs the whole suite; nothing from an earlier stage may break.
- Browser behaviour (copy on the phone, swipe, autosave on lock) is checked by hand in each
  stage's "Done when", and in headless Firefox at 375px where it can be.

---

## 7. Reliability details

- **Startup** (`create_app`): make `files/ thumbs/ tmp/` under the data dir, **empty `tmp/`**
  (a restart mid-upload leaves a partial there and nowhere else), run migrations. Log one
  line with counts. No orphan sweep on every start — S11 adds a `python -m app.cli check`
  that lists (and with `--fix` removes) disk files without rows.
- **SQLite:** one connection per request (`sqlite3.connect(..., timeout=10)`), `PRAGMA
  journal_mode=WAL` once at startup, `foreign_keys=ON` and `busy_timeout` per connection.
  Writes are short. Routes are plain `def` (FastAPI runs them in a thread pool), except the
  upload and file-serving routes, which are `async` so a 2 GB stream never holds a thread.
- **Uploads:** stream `request.stream()` to `tmp/<uuid>.part` in 1 MB chunks, counting bytes;
  over the limit or client disconnect → delete the part file, 413/400. On success: `fsync`,
  `os.replace` into `files/<id[:2]>/<id>` (same filesystem, atomic), then insert the row. If
  the insert fails, delete the moved file. `shutil.disk_usage` checked before starting:
  if free space < Content-Length + 512 MB → 507 "Vault disk full".
- **Autosave:** PATCH 800 ms after typing stops, on `visibilitychange` to hidden, and on
  `pagehide`, with `keepalive: true`. Last write wins (acceptable per S5).

---

## 8. Gotchas and how we handle them

The eight from the brief, then the ones found while writing this plan. Items that only matter
on an iPhone are kept (D1 decision) but marked.

1. **Clipboard API needs HTTPS.** `tailscale serve` gives the vault a real certificate (S3).
   Until then, and as a fallback, `app.js` copies from an off-screen textarea with
   `execCommand('copy')`, already proven in D3 on plain http.
2. **The clipboard write must happen inside the tap** (strict on iPhone Safari, also true for
   the Android fallback). The full text is already in the page in `.clip__source`, so COPY
   never awaits a fetch. This settles the D3 known issue: hidden clip content stays in the
   page HTML — behind login, over HTTPS, with `Cache-Control: no-store`, masked on screen.
   Fetching it on tap would break copy on the fallback path for no real gain on a
   single-user vault.
3. **EXIF rotation.** `ImageOps.exif_transpose()` before resizing. Android cameras need it too.
4. **HEIC (iPhone).** Pillow can't open it → `thumbs.make()` returns `None`, the endpoint
   404s, the template shows the type icon. Any exception in thumbnailing is caught and
   logged by file id. Never a 500.
5. **Video seeking needs HTTP Range (206).** Starlette's `FileResponse` handles `Range` in
   the versions FastAPI currently pins. S6 proves it with a test (206, `Content-Range`, exact
   bytes). If the pinned version doesn't, `storage.py` gets a ~40-line single-range handler.
6. **Large uploads stream to disk** — see §7. Nothing reads a file body into memory.
7. **Active content inline = same-origin XSS.** The allowlist in §5 #11, `nosniff`, and a
   `sandbox` CSP on file responses. **PDF exception:** Chrome refuses to render a PDF served
   with `CSP: sandbox`, and `X-Frame-Options: DENY` would stop the desktop embed. PDFs get
   `Content-Type: application/pdf`, `nosniff`, `X-Frame-Options: SAMEORIGIN`, CSP
   `frame-ancestors 'self'` and no sandbox. A PDF is not HTML, so this is safe; S8 checks the
   embed in Chrome and Firefox on the laptop.
8. **Copying a live SQLite file can corrupt the backup.** `backup.py` uses
   `sqlite3.Connection.backup()` into a temp file, runs `PRAGMA integrity_check` on the copy,
   then archives.
9. **Multipart uploads would double every byte on disk.** FastAPI's `UploadFile` spools the
   whole multipart body to the *container's* `/tmp` before the route runs — a 2 GB upload
   writes 2 GB into the container layer, then we copy it again, and the size limit can only
   be checked after the fact. A raw-body `POST` streamed from `request.stream()` avoids all
   three problems and is what `XMLHttpRequest.send(file)` does naturally, with progress
   events. `python-multipart` stays, for the login form only.
10. **`./data` permissions.** A non-root container user with a different uid can't write to
    `./data` created by you (uid 1000), or it creates files you can't delete. Compose runs
    the container as `${UID:-1000}:${GID:-1000}`, and the README says to `mkdir data backups`
    before the first `up`.
11. **Behind `tailscale serve` every request comes from the same address** (the proxy, then
    Docker's gateway), so a per-IP lockout is really a global one. We make that explicit: one
    bucket. Only your own tailnet devices can reach the login page, so the worst case is an
    attacker-free 15-minute wait after 5+ wrong tries on your own phone. `X-Forwarded-For`
    is not trusted.
12. **Absolute URLs would be `http://`.** The app sees plain HTTP from the proxy, so
    `request.url_for()` builds `http://…` links that break on the HTTPS page. Templates use
    root-relative paths (`/static/css/app.css`, `/files/abc…`), redirects use relative
    `Location`s. The one absolute URL — the photo viewer's "Copy link" — is built in JS from
    `location.origin`.
13. **Uploads die if you leave the page.** Pages are real page loads, so an in-flight
    `XMLHttpRequest` is cancelled by navigation. DESIGN §3.13 said the panel "survives moving
    between screens"; that would need a single-page app or a service worker. v1: the panel
    stays on the page it started on, a `beforeunload` warning appears while anything is
    uploading, and tapping a tab while uploading asks first. DESIGN updated.
14. **Timezone.** The container clock is UTC, so "Today, 09:15" would be 5½ hours off.
    Stored times stay UTC; `web.py` formats with `zoneinfo.ZoneInfo(VAULT_TIMEZONE)`. The
    Dockerfile installs the Debian `tzdata` package (an OS package, not a Python dependency)
    because the slim image may lack zone files — S1 verifies.
15. **`UNIQUE(parent_id, name)` doesn't work at the root**, because NULLs never collide.
    The expression index `IFNULL(parent_id, 0)` in §2 fixes it.
16. **Backups multiply disk use.** Every archive is a full copy of every file. With 14 kept
    (the S10 brief), a 50 GB vault needs 700 GB of backups on the same disk that a disk
    failure would take anyway. Default `BACKUP_KEEP=3`; `backup.py` checks free space first
    and refuses with a clear message; the README pushes the weekly copy to an external drive.
    Archives are plain **`.tar`, not `.tar.gz`**: photos, videos, PDFs and zips are already
    compressed, so gzip burns minutes of CPU to save ~1%.
17. **Access logs leak search terms and names.** `--no-access-log`; the app logs its own
    one-line events without content (§5 #16).
18. **Docker must start on boot** or the vault is gone after a power cut:
    `sudo systemctl enable docker` in the README, plus `restart: unless-stopped`.
19. **`tailscale serve` request size.** A 2 GB body passes through the Tailscale proxy.
    S3/S6 upload a real 2 GB file over `ts.net` from the laptop to confirm there's no limit
    or timeout; if there is, `MAX_UPLOAD_SIZE_MB` is lowered and the README says why.
20. **Case-insensitive sorting and search are ASCII-only** in SQLite (`NOCASE`, `LIKE`).
    `रसीद.pdf` still sorts and matches exactly; only case-folding of non-English letters is
    missing. Acceptable for v1; noted, not fixed.
21. **Chrome on Android can't show a PDF inside a page.** Settles the D3 known issue with no
    new dependency: on desktop the preview embeds `/api/files/{id}/view` in an `<iframe>`; on
    a phone (no fine pointer) it shows the details block with **Download** and **Open PDF**
    (opens `/view` in a new tab, where Android hands it to the PDF app). No page-1 render, no
    `pypdfium2`. The D3 mockup's page image is not built.

---

## 9. Where this plan differs from the playbook's stage briefs

Settled here so no stage has to decide mid-build. `DESIGN.md` is the reviewed spec, so where
a brief and the design disagree, the design wins unless noted.

| Stage brief says | Plan does | Why |
|---|---|---|
| D5: `pinned` column | `favorite` column | D4: one word — Favorite — in UI, code and DB |
| D5: `schema.sql` plus migrations | only numbered migrations, `001_initial.sql` is the schema | one source of truth; a separate schema.sql drifts from the migrations |
| S2: lockout per client IP | one global bucket | behind `tailscale serve` all clients share an address (gotcha 11) |
| S2: password set only via CLI | CLI **and** Change password in Settings (`/api/password`, needs the current password) | DESIGN §3.14 makes it the Settings primary action. CLI stays for first setup and "forgot password" |
| S4: `static/js/copy.js` | copy stays in `static/js/app.js` | already built and tested in D3; one JS file until it passes ~1,000 lines |
| S4: edit a clip in a bottom sheet / modal | full-screen editor with autosave, shared with notes | DESIGN §3.9: clips can be 100 KB |
| S4: copy failure text "Couldn't copy, press and hold to select" | DESIGN's "Press and hold to copy — open the vault over HTTPS for one-tap copy." | tells you the fix, not just the failure |
| S5: notes list pinned first | notes, clips, links: favorites first, then newest | same rule on all three lists |
| S6: `POST /api/files` multipart, many files | one raw-body request per file, 2 in parallel | gotcha 9 |
| S6: new files appear without reload | the list refreshes from `?partial=1` after each upload | no row HTML built in JS |
| S7: sort only in the URL | sort in the URL **and** saved on the folder (`folders.sort`, root in `settings`) | DESIGN §3.3: "the choice sticks per folder". Tapping the current sort again flips direction |
| S7/DESIGN: select mode bar Move / Download / Delete | Move / Delete | downloading many files at once needs a zip builder or fights the browser's multi-download blocking. Download stays per file |
| S8: PDF embedded on desktop, button on phone | same — and the page-1 image in the D3 mockup is dropped | gotcha 21, no new dependency |
| S8: toggle to include videos in Photos | videos always in the grid, no toggle | DESIGN §3.5 |
| D3 mockup: video tile shows duration `0:42` | play badge only | reading a duration needs ffmpeg or an MP4 parser |
| S8: viewer actions | DESIGN's plus **Copy link** (`location.origin + /files/<id>`) with the toast "Only works when logged in to your vault" | SPEC §5 asks for it; nothing public |
| S9: Home = pinned (8) + recent files (8) + recent notes (5) + section tiles | DESIGN §3.2: Favorites (6) + Recent mixed (10), no tiles | reviewed in D4; tiles would push Favorites below the fold at 375px |
| DESIGN: "See all" on Recent | removed; "See all" stays on Favorites | there is no Recent page to go to (D4 open question). Finding an older file is search, or Files sorted by Date added |
| S9: hidden clips match search, masked | hidden clips match by **title only** | DESIGN §3.12: hidden content never feeds search |
| S9: `/api/search` JSON for the UI | UI uses `/search?partial=1`; `/api/search` exists for tests and the SPEC | one results template |
| S10: BACKUP_KEEP 14, `.tar.gz` | 3, `.tar` | gotcha 16 |
| DESIGN §3.13: upload panel survives navigation | stays on its page, warns before leaving | gotcha 13 |
| SPEC: `INITIAL_PASSWORD` in `.env` | not supported | a plaintext password in a file (§4) |

---

## 10. Dependencies

Runtime, exactly the approved list — versions pinned in `requirements.txt` in S1:
`fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `argon2-cffi`, `itsdangerous`, `pillow`.
Dev: `pytest`, `httpx`.

**No new Python dependencies.** Considered and rejected: `pypdfium2` (PDF page render —
gotcha 21 makes it unnecessary), `pillow-heif` (no iPhone, backlogged), `python-dotenv`
(Compose's `env_file` already loads `.env`; tests pass settings directly), an ORM, a
migration tool.

OS package in the Docker image: `tzdata` only (gotcha 14).
