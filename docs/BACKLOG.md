# Backlog

Ideas that are **not** part of version 1. Add to this list instead of expanding a stage.

Revisit only after the vault has been in daily use for a few weeks.

## Likely worth doing, roughly in order of everyday value
- [ ] **Install as an app** (PWA manifest + icons) so the vault opens from the phone home screen without browser chrome.
- [ ] **Share into the vault from other apps.** Android: Web Share Target. iPhone: an iOS Shortcut that posts to the upload API.
- [ ] **Trash with 30-day restore** instead of immediate delete.
- [ ] **Paste to upload** on desktop: paste a screenshot or text and it becomes a file or a clip.
- [ ] **Markdown preview** for notes (needs a safe renderer — a dependency decision).
- [ ] **HEIC thumbnails** via `pillow-heif`. iPhone-only format — no use until there is an
      iPhone in the picture.
- [ ] **Video thumbnails** via ffmpeg in the Docker image. Decided against in D1: a large
      dependency for a nicety. Videos show an icon with a play badge until then.
- [ ] **Resumable / chunked uploads.** Decided against in D1 — needs an upload-session table
      and client-side state. Until then a failed upload retries from the start, which on a
      home network is usually fine. Revisit if large uploads over mobile data fail often.
- [ ] **SQLite FTS5 search** if the simple LIKE search ever feels slow.
- [ ] **Automatic off-machine backup copy** to an external drive or another computer on the tailnet.

## Explicitly rejected
- Multi-user accounts, roles, permissions
- Public sharing links
- Cloud storage or cloud backup
- Rich text editing
- Anything that fetches from the internet at runtime

## New ideas
_(add below, one line each, with the date and why you wanted it)_
- 2026-09-17 (S7): **Drag a row onto a folder to move it (desktop).** Optional in the S7 brief; left out so the checkbox → Move path stays the only one to test. Add if moving on the laptop feels slow.
- 2026-09-17 (S8): **Select mode on Photos** (DESIGN §3.5: header ⋯ → Select → Move / Delete). Not in the S8 brief; for now, select in Files or delete one at a time in the viewer.
- 2026-09-21 (S11): **Page the long lists.** Notes, Clipboard and Links render every item: 500 notes is a 370 KB page (32 KB gzipped, 12 ms). Fine today; add "load more" if it ever feels slow on the phone.
- 2026-09-21 (S11): **Automated QA at a true 375px.** Headless Firefox clamps its window to 500 CSS px, so 375 is only ever checked by hand on the phone. A second browser (Chromium) in the dev setup would fix that.
- 2026-09-21 (S11): **Answer HEAD as well as GET** on pages (FastAPI routes are GET-only, so `curl -I` returns 405). Harmless today.

