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
(To be filled in during stage S4 — Clipboard is the reference implementation. Every later feature copies its shape.)
