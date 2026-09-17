# Personal Vault: project rules

Read `docs/PROGRESS.md` before starting any task. The full brief is `docs/SPEC.md`. The stage-by-stage plan is `docs/PLAYBOOK.md`.

## What this is
A single-user personal vault (files, photos, notes, clipboard, links) that runs on my office computer and is reached from my own devices over Tailscale. A personal utility, not a SaaS product.

Priority order: **security basics → reliability → simplicity → everyday usability → visual polish.**

## Never build
Multi-user accounts, roles or permissions, public sharing links, cloud services, microservices, message queues, or any "enterprise" auth (SSO, 2FA, password-reset email). One password is enough.

## Stack
- Python 3.12, FastAPI, Jinja2 server-rendered pages
- Small vanilla JS files for interactivity. No React, no npm, no build step
- SQLite via the built-in `sqlite3` module. No ORM
- Docker + Docker Compose
- All CSS, JS, fonts and icons served from `/static`. No CDNs, no external requests at runtime

Do not add a dependency without telling me why and waiting for my OK.

## Hard rules
- Login is required on every route by default. Only `/login`, `/static` and `/healthz` are public.
- User-provided names (filenames, folder names) are **display text only** and never become filesystem paths. Files are stored on disk under generated UUIDs.
- Uploaded HTML, SVG, XML and JS are never served inline. Force download.
- No inline `<script>` or `style=` attributes in templates, so a strict Content-Security-Policy keeps working.
- Never log or display passwords, note bodies or clipboard content.
- Secrets live in `.env`, which is gitignored. Never commit them.

## Mobile first
Every screen must work at 375px wide. Tap targets at least 44×44px. Form inputs at least 16px font size so iPhone doesn't zoom. Respect iPhone safe-area insets on the bottom nav.

## Working agreement
- One stage at a time, from `docs/PLAYBOOK.md`. Do not start the next stage without being asked.
- Every stage ends with a **running app and passing tests**. Never break an earlier feature.
- Do not expand scope. New ideas go in `docs/BACKLOG.md`, not into the code.
- Prefer the boring, obvious solution. Fewer files, fewer abstractions, less configuration.
- At the end of every stage: update `docs/PROGRESS.md` (done / next / known issues) and give me the exact commands to verify it myself.
- When something in the plan looks wrong, say so before writing code rather than silently doing it differently.

## How a feature is structured
Clipboard (S4) is the reference. Copy its shape; don't invent a new one.

- **One module:** `app/<feature>.py` (`app/clips.py`), in this order: SQL functions, page routes, `/api` routes. Include its router in `main.py`. Split only past ~500 lines.
- **SQL functions** take `conn` first and return plain dicts (`to_clip()` turns 0/1 into bools). Only `?` parameters; LIKE terms via `db.like_pattern()` with `ESCAPE '\'`; lists end `ORDER BY favorite DESC, updated_at DESC, id DESC`. Routes open `with db.connect(settings.db_path) as conn:`. Timestamps only from `db.now()`.
- **Validation** in one `check_fields(payload, allowed)`: JSON body as `payload: dict = Body(...)`, exact types (`bool` is not `1`), lengths match the SQL CHECKs. Failures `raise ApiError("Sentence the user can act on.", 4xx)` → `{"error": "…"}`. Missing → 404 with "That <thing> no longer exists."
- **API:** `GET /api/<things>?q=` → `{<things>: [...]}`; `POST` → 201 object; `PATCH /{id:int}` any subset → object; `DELETE` → 204. Every field always present.
- **Pages:** list at `/<section>`, `POST /<section>/new` → 303 to the editor, editor at `/<section>/{id:int}`. `{id:int}` in paths, so a bad id is a 404 page. Page templates `{% extends layout %}`, so `?partial=1` returns just the content block.
- **Templates:** row markup is a macro in `macros.html` (`clip_row`), used by the list now and Home/Favorites/Search later. Sheets go in `{% block dialogs %}`; the delete confirm is in `base.html`. A row's ⋯ button carries `data-item="/api/<things>/<id>"`, `data-sheet-title`, `data-edit`, and `data-favorite` / `data-clip-hidden` when on. Full-screen editors use `editor.html`; other forms are a page with `no_tabbar=True` (`link_form.html`). Import macros `with context` (the date filters need the request).
- **JS** (`static/js/app.js` only): every call through `api(method, url, body)`, which throws an Error whose message is the toast text. After a change on a list: `refreshMain()` (fetches `?partial=1`), then `toast('…')`. Errors: `failed(error)` (401 → login, else error toast). Never build row HTML in JS; only `textContent`.
- **Logging:** ids only (`Clip 7 created`). Never titles, bodies, contents or search terms.
- **Tests:** `tests/test_<feature>.py`: create, list order, search (incl. LIKE wildcards), update, delete, each validation error, logged-out 401/302, foreign Origin 403, escaping, partial, no inline script/style, and logs without content.
