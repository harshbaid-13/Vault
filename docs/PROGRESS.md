# Progress

**Current stage:** D2 (visual system)
**Last updated:** 2026-09-12, after D1

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
- [ ] D2 — Visual system → `docs/DESIGN.md` Part 2 + `static/css/tokens.css`
- [ ] D3 — Clickable mockups → `/mockups`
- [ ] D4 — Design review (repeat until happy)
- [ ] D5 — Technical plan → `docs/TECH_PLAN.md`

### Build
- [ ] S1 — Walking skeleton (Docker, layout, DB, health check)
- [ ] S2 — Login and logout
- [ ] S3 — Phone access over Tailscale HTTPS → `docs/TAILSCALE.md`
- [ ] S4 — Clipboard with COPY *(reference implementation)*
- [ ] S5 — Notes and Links
- [ ] S6 — Files: upload, download, rename, delete
- [ ] S7 — Folders, move, sort
- [ ] S8 — Previews, thumbnails, Photos gallery
- [ ] S9 — Home dashboard, Favorites, universal search
- [ ] S10 — Backup, restore, README
- [ ] S11 — Hardening and final checks

## Done so far
- **D1** — `docs/DESIGN.md` Part 1: UX. Navigation, 14 screens with 375px sketches,
  5 key flows with tap counts, shared interaction patterns, and what v1 leaves out.
  No code written.

## Next
Run stage D2 from `docs/PLAYBOOK.md` (visual system → `docs/DESIGN.md` Part 2 +
`static/css/tokens.css`). D1's open questions are all answered and folded into
`docs/DESIGN.md`; nothing is blocking.

## Known issues
_(none yet — no code exists)_

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
