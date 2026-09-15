# Progress

**Current stage:** D4 (design review) — round 1 done, waiting for phone feedback
**Last updated:** 2026-09-15, after D4 round 1

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
  on Change password. `docs/DESIGN.md` updated to match. Still not tried on the phone.

## Next
D4 round 2: open the mockups on the Android phone and the laptop, write down what felt wrong,
slow, ugly or confusing, and bring it back with answers to the questions under Known issues.

## Known issues
- **"See all" on Home's Recent has nowhere to go.** Recent mixes files, notes and clips, but
  it links to Files (sorted by name). DESIGN §4 relies on it for "find a PDF from last week".
  Decide in D4: drop the link, or add a plain newest-first "Recent" list page (a 15th screen).
- **PDF preview on Android.** Chrome on Android cannot show a PDF inside a page, so the
  "embedded viewer" in DESIGN §3.4 would be blank on my phone. The mockup shows a page-1
  image instead, which the real app can only do by rendering it on the server — a new
  dependency (e.g. `pypdfium2` or poppler). Decide in D4/D5: render page 1, or show the
  details block with Open/Download only.
- **Hidden clip content is in the page HTML** (a hidden textarea), because COPY must work
  without a fetch — an async fetch breaks the plain-http copy fallback. It is masked on
  screen, never in search snippets. D5 decides whether that is acceptable or whether hidden
  clips copy via a fetch once HTTPS (S3) makes the async Clipboard API reliable.
- **Not mocked:** select mode, rename/move/new-link/change-password forms, the clip editor
  (Edit opens the note editor, same layout), swipe-down to dismiss a sheet, the login
  error/lockout state, the offline banner, loading skeletons. Search results are static.
  Those actions show a toast saying so.
- The photo viewer mockup puts every photo in one page (lazy-loaded). The real viewer
  should render only the current photo and its neighbours.

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
