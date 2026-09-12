# Design — Personal Vault

**Part 1: UX.** Navigation, screens, flows and interaction patterns. No code, no colours,
no type scale — the visual system is Part 2 (stage D2), clickable mockups are D3.

Rules that constrain everything here live in `CLAUDE.md`. The brief is `docs/SPEC.md`.

---

## 1. What this is, and the three things I do most

A single-user vault on an always-on office computer, reached from my own devices over
Tailscale. It should feel like a good notes app, not a dashboard. Calm, fast, obvious.

The three most common tasks, ranked. Every decision below favours these, in this order.

**1. Copy a saved text on my phone** — a Wi-Fi password, a UPI ID, an address.
→ Clipboard gets a permanent slot in the bottom bar. COPY is a full-size button on every
row, never buried in a menu. Copying takes two taps from anywhere and never requires
opening the item. Sensitive items can be masked so the screen is safe to hold up.

**2. Send a photo or file from phone to vault** — a receipt, a document photo, a PDF.
→ Upload is a raised centre button in the bottom bar, present on every screen, one tap
from anywhere. It opens the phone's own sheet (Camera / Photo Library / Files), and the
upload runs in a panel that does not block the rest of the app.

**3. Find something I uploaded recently** — a PDF from last week, a photo from yesterday.
→ Home opens on Recent, newest first, no clicks needed. Everything is sorted
newest-first by default everywhere. Search reaches every section from one field.

Everything else in the vault — folders, note editing, links, favourites — is real, but it
is not what the layout optimises for.

---

## 2. Navigation

### Mobile (the primary case)

A fixed bottom tab bar, five slots, on every screen except Login and the Photo viewer.

```
┌───────────────────────────────────────┐
│                                       │
│            (page content)             │
│                                       │
├───────────────────────────────────────┤
│  ⌂      ▤     ╭───╮    ▣      ⋯      │
│ Home  Files   │ ＋ │  Clip   More    │
│               ╰───╯                   │
└───────────────────────────────────────┘
     ↑ safe-area inset below
```

- **Home · Files · ＋ · Clipboard · More**
- `＋` is a raised circular button, visually distinct from the four tabs. It is an action,
  not a destination — it opens the upload sheet over whatever screen you are on, and the
  screen behind it does not change.
- **More** opens a bottom sheet: Photos · Notes · Links · Favorites · Settings · Log out.
- The bar sits above the iPhone home indicator (safe-area inset). Each tab is at least
  44×44px; the `＋` button is 56px.
- Why these five: Clipboard is task 1 and Upload is task 2, so both are permanent. Home
  answers task 3. Files earns its slot as the thing everything else lands in. Photos loses
  its slot to Upload — photos arrive far more often than they are browsed, and the grid is
  still two taps away via More.

**Search on mobile** is a magnifier in the top bar of Home, Files, Photos, Notes,
Clipboard and Links. It searches the section you are in; the results screen has an
"Everywhere" toggle to widen it to the whole vault.

### Desktop

A persistent left sidebar, no hamburger:

```
┌──────────────┬────────────────────────────────────────────┐
│  MY VAULT    │  🔍 Search everything          ＋ Upload   │
│              ├────────────────────────────────────────────┤
│ ＋ Upload    │                                            │
│              │              (page content)                │
│ ⌂  Home      │                                            │
│ ▤  Files     │                                            │
│ ◫  Photos    │                                            │
│ ✎  Notes     │                                            │
│ ▣  Clipboard │                                            │
│ ⛓  Links     │                                            │
│ ★  Favorites │                                            │
│              │                                            │
│ ⚙  Settings  │                                            │
└──────────────┴────────────────────────────────────────────┘
```

- Every section is visible at once; nothing hides behind More.
- Upload appears twice on purpose: top of the sidebar, and in the header of Files and
  Photos where it is contextual (it uploads *into the folder you are looking at*).
- Search is a real field in the header, always visible, focused with `/`.
- The sidebar collapses to the mobile bottom bar below 900px. There is no third layout;
  tablets get the desktop one in portrait if they are wide enough, otherwise mobile.

---

## 3. Screens

Fourteen screens. Sketches are at 375px.

### 3.1 Login

**Purpose:** the only public screen. One password, nothing else.
**On it:** vault name, password field, Log in button, error line.
**Primary:** Log in. **Secondary:** none — no signup, no reset, no "remember me" checkbox
(the session cookie already lasts).
**Empty state:** n/a.
**After too many failures:** the button disables and the line reads *"Too many attempts.
Try again in 60 seconds."* with a live countdown.

```
┌─────────────────────────────┐
│                             │
│                             │
│          MY VAULT           │
│                             │
│  ┌───────────────────────┐  │
│  │ Password              │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │       Log in          │  │
│  └───────────────────────┘  │
│                             │
│  Wrong password.            │
│                             │
└─────────────────────────────┘
```

The error text is always the same for a wrong password — it never says whether anything
else was the problem.

### 3.2 Home

**Purpose:** answer three questions without a single tap — what can I copy, what did I
pin, what arrived recently.
**On it:** Pinned section (mixed types, max 6), Recent section (mixed types, max 10),
search, upload.
**Primary:** whatever the row is — COPY for a clip, open for a file.
**Secondary:** "See all" on each section heading.
**Empty state:** *"Nothing here yet. Tap ＋ to add your first file, or save a clip you copy
often."*

```
┌─────────────────────────────┐
│ MY VAULT              🔍    │
├─────────────────────────────┤
│ PINNED                      │
│ ┌─────────────────────────┐ │
│ │ ▣ Wi-Fi Password        │ │
│ │ ••••••         [ COPY ] │ │
│ ├─────────────────────────┤ │
│ │ ▤ passport.pdf          │ │
│ │ 2.4 MB          [ OPEN ]│ │
│ └─────────────────────────┘ │
│                             │
│ RECENT              See all │
│ ┌─────────────────────────┐ │
│ │ ◫ vacation.jpg   Sep 10 │ │
│ │ ▤ project.pdf    Sep 10 │ │
│ │ ✎ shopping list  Sep  9 │ │
│ └─────────────────────────┘ │
│                             │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Pinned comes first because a pinned item is something I chose; Recent is only the machine
guessing.

### 3.3 Files (inside a folder)

**Purpose:** a file manager. Folders first, then files.
**On it:** breadcrumb, sort control, folder rows, file rows (name, size, date, ★ if
favourited, ⋯ menu).
**Primary:** tap a row — folder opens, file goes to preview.
**Secondary:** ⋯ per row (Rename, Move, Favorite, Download, Delete); header menu (New
folder, Select, Sort); Upload uploads into *this* folder.
**Empty state:** *"This folder is empty. Tap ＋ to add something."*

```
┌─────────────────────────────┐
│ ‹ Home / Documents    🔍 ⋯  │
├─────────────────────────────┤
│ Name ▾                      │
│ ┌─────────────────────────┐ │
│ │ 📁 Tax 2025          ›  │ │
│ │ 📁 Manuals           ›  │ │
│ ├─────────────────────────┤ │
│ │ ▤ passport.pdf       ⋯  │ │
│ │   2.4 MB · Sep 10    ★  │ │
│ ├─────────────────────────┤ │
│ │ ▤ lease.docx         ⋯  │ │
│ │   88 KB · Sep 8         │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Two lines per row, not a table. Tables do not survive 375px. Sort options: Name, Date
added, Size, Type — the choice sticks per folder.

**Select mode** (desktop: click checkboxes; mobile: header ⋯ → Select) turns the header
into a count and the bottom bar into Move / Download / Delete.

### 3.4 File preview

**Purpose:** see enough to know it is the right file, then act.
**On it:** filename, type, size, upload date, the preview itself, action row.
**Preview by type:** image → the image; PDF → embedded viewer; text/markdown/code → plain
text in a scroll box with a Copy button; video/audio → the browser's own player; everything
else → a large type icon and the file's details.
**Primary:** Download. **Secondary:** Favorite, Rename, Move, Delete, Copy name.
**Empty state:** n/a. **If the preview cannot render:** *"No preview for this type."* and
the details block stays.

```
┌─────────────────────────────┐
│ ‹ Files               ★  ⋯  │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │     (PDF page 1)        │ │
│ │                         │ │
│ └─────────────────────────┘ │
│ passport.pdf                │
│ PDF · 2.4 MB · Sep 10, 2025 │
│ ┌─────────────────────────┐ │
│ │      ⭳  Download        │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

HTML, SVG, XML and JS never render here — they show the details block and download only.
That is a hard rule in `CLAUDE.md`, and the screen must not fight it.

Video and audio play in the browser's built-in player, which means the server must answer
HTTP **Range** requests. Without them the player can only play from the start — no seeking,
no scrubbing — and on a long video it downloads the whole file before it starts. This is
not iPhone-specific; every browser needs it.

### 3.5 Photos grid

**Purpose:** browse images visually, not as filenames.
**On it:** square thumbnails, three across at 375px, grouped under month headings, newest
first.
**Primary:** tap → Photo viewer. **Secondary:** header ⋯ → Select (then Download / Move /
Delete); Upload adds photos.
**Empty state:** *"No photos yet. Tap ＋ to add some from your camera roll."*

```
┌─────────────────────────────┐
│ Photos                🔍 ⋯  │
├─────────────────────────────┤
│ September 2025              │
│ ┌───┐ ┌───┐ ┌───┐           │
│ │   │ │   │ │   │           │
│ └───┘ └───┘ └───┘           │
│ ┌───┐ ┌───┐ ┌───┐           │
│ │   │ │   │ │   │           │
│ └───┘ └───┘ └───┘           │
│ August 2025                 │
│ ┌───┐ ┌───┐ ┌───┐           │
│ │   │ │   │ │   │           │
│ └───┘ └───┘ └───┘           │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Photos are files — the same rows that appear in Files. This is a view, not a separate
store. A photo inside a folder still appears here.

**Videos** appear in this grid too, but with no generated thumbnail — a video icon with a
play badge and the duration, on a plain tile. Real video thumbnails need ffmpeg in the
Docker image, which is a large dependency for a nicety; it is in `docs/BACKLOG.md`.

Image thumbnails are **EXIF-rotated** when generated. Phone cameras — Android included —
record orientation as a tag rather than rotating the pixels, so a thumbnail that ignores it
shows a sideways photo.

### 3.6 Photo viewer

**Purpose:** look at one image properly.
**On it:** the image on a dark ground, edge to edge. Chrome (back, ★, ⋯) fades in on tap
and out after a moment. No bottom tab bar — the image gets the whole screen.
**Primary:** look. **Secondary:** swipe left/right for next/previous (desktop: ← →),
Download, Rename, Favorite, Delete, Esc/back to grid.
**Empty state:** n/a.

```
┌─────────────────────────────┐
│ ‹                    ★   ⋯  │
│                             │
│                             │
│         (the photo)         │
│                             │
│                             │
│                             │
│ vacation.jpg · Sep 10       │
└─────────────────────────────┘
```

### 3.7 Notes list

**Purpose:** find a note fast.
**On it:** rows of title + first line of the body + date, newest-modified first, ★ shown.
**Primary:** tap → editor. **Secondary:** ⋯ (Favorite, Delete); New note button.
**Empty state:** *"No notes yet. Tap ＋ to write one."*

```
┌─────────────────────────────┐
│ Notes            🔍  ＋ New │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Shopping list        ★  │ │
│ │ milk, bread, …  Sep 9   │ │
│ ├─────────────────────────┤ │
│ │ Car service             │ │
│ │ Booked for the… Sep 4   │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Here `＋ New` in the header creates a note; the bottom-bar `＋` still uploads a file. The
header button is the contextual one, and it is labelled.

### 3.8 Note editor

**Purpose:** write with nothing in the way.
**On it:** title field, body field, a saved-state line, ★ and ⋯ in the header. No toolbar,
no formatting buttons — plain text in v1.
**Primary:** typing. **Secondary:** Copy all, Favorite, Delete, back.
**Saving:** autosave, quietly. The line under the header reads *Saving…* then *Saved* then
fades to the modified time. It never blocks typing and there is no Save button.
**Empty state:** the body placeholder is *"Start writing…"*.

```
┌─────────────────────────────┐
│ ‹ Notes               ★  ⋯  │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Shopping list           │ │
│ └─────────────────────────┘ │
│ Saved · Sep 9, 18:02        │
│ ┌─────────────────────────┐ │
│ │ milk                    │ │
│ │ bread                   │ │
│ │ coffee                  │ │
│ │                         │ │
│ │                         │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

The bottom bar is hidden while the keyboard is up, so the body keeps its room.

### 3.9 Clipboard

**The most important screen.** It is the reference implementation for every later feature
(stage S4), so its shape is the house style.

**Purpose:** get a saved text into the device clipboard in as few taps as possible.
**On it:** rows of title + a 2–3 line preview of the content (or `••••••` if hidden) + a
full-width COPY button. Favourites float to the top, then newest-modified.
**Primary:** COPY. **Secondary:** tap the row → edit; ⋯ (Edit, Favorite, Hide/Show,
Delete); `＋ New` in the header.
**Empty state:** *"Nothing saved yet. Tap ＋ New for things you copy often — Wi-Fi
password, address, UPI ID."*

```
┌─────────────────────────────┐
│ Clipboard        🔍  ＋ New │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Wi-Fi Password       ★  │ │
│ │ ••••••••           👁 ⋯ │ │
│ │ ┌─────────────────────┐ │ │
│ │ │       COPY          │ │ │
│ │ └─────────────────────┘ │ │
│ ├─────────────────────────┤ │
│ │ SSH key (laptop)     ⋯  │ │
│ │ ssh-ed25519 AAAAC3Nz    │ │
│ │ aC1lZDI1NTE5AAAAIB4x    │ │
│ │ Qk9v7rL2mN…  ▒▒fade▒▒   │ │
│ │ ┌─────────────────────┐ │ │
│ │ │       COPY          │ │ │
│ │ └─────────────────────┘ │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Non-negotiables for this screen:

- COPY is a real button, full row width, at least 44px tall. It is never an icon at the
  end of a row.
- COPY works on a hidden item **without revealing it**. The eye toggles visibility for
  looking; the two are independent.
- Hidden is per-item and sticky. It re-hides when the screen is left and re-entered.
- A clip can hold **long text** — a paragraph, an SSH key, a config block — up to about
  100 KB. The row shows only the first 2–3 lines, fading out at the bottom edge rather than
  cutting mid-character, so a long clip never pushes the next COPY button off screen.
- **COPY always copies the entire clip, never the visible preview.** This is the easiest
  bug to ship here and the hardest to notice: everything looks right and the pasted text is
  silently truncated. It deserves a test of its own in S4.
- Because clips are long, the editor is a full screen with a large body field, not a
  one-line dialog. It autosaves like the note editor.
- After a copy: toast *Copied ✓*, and the button itself reads *Copied ✓* for two seconds.
- If the Clipboard API is unavailable (not HTTPS), the button selects the text instead and
  the toast reads *"Press and hold to copy — open the vault over HTTPS for one-tap copy."*
  This is the failure the Tailscale HTTPS setup in S3 exists to prevent.

### 3.10 Links

**Purpose:** saved URLs, opened in one tap.
**On it:** title, hostname, optional description, ★, date.
**Primary:** tap → opens in a new tab. **Secondary:** ⋯ (Copy URL, Edit, Favorite,
Delete); `＋ New`.
**Empty state:** *"No links yet. Tap ＋ New to save one."*

```
┌─────────────────────────────┐
│ Links            🔍  ＋ New │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Router admin         ★  │ │
│ │ 192.168.1.1          ⋯  │ │
│ ├─────────────────────────┤ │
│ │ Electricity bill        │ │
│ │ portal.example.com   ⋯  │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Showing the hostname under the title is the cheap way to see where a link actually goes.
No favicons — that would mean fetching from the internet at runtime, which is forbidden.

### 3.11 Favorites

**Purpose:** everything I pinned, in one place, regardless of type.
**On it:** the same rows used elsewhere — a clip row keeps its COPY button, a file row
opens a preview, a link opens the URL. Optional type filter chips across the top.
**Primary:** the row's own action. **Secondary:** ⋯ (including Unfavorite).
**Empty state:** *"No favourites yet. Tap ★ on anything you use often."*

```
┌─────────────────────────────┐
│ Favorites             🔍    │
├─────────────────────────────┤
│ [All] Files Photos Notes …  │
│ ┌─────────────────────────┐ │
│ │ ▣ Wi-Fi Password        │ │
│ │ ••••••         [ COPY ] │ │
│ ├─────────────────────────┤ │
│ │ ▤ passport.pdf      ›   │ │
│ ├─────────────────────────┤ │
│ │ ⛓ Router admin      ›   │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

### 3.12 Search results

**Purpose:** one field, the whole vault.
**On it:** the query, type filter chips, results grouped by type with counts. Live as you
type after 2 characters.
**Primary:** the row's own action — a clip found in search still copies from the results
list, without opening it.
**Secondary:** the Everywhere / this-section toggle; filter chips.
**Empty state (no query):** recent searches, or nothing at all.
**Empty state (no results):** *"Nothing matches "lease". Try part of a filename or a
word from the text."*

```
┌─────────────────────────────┐
│ ‹  lease              ✕     │
├─────────────────────────────┤
│ [All] Files Notes Clips …   │
│ FILES (2)                   │
│ │ ▤ lease.docx    Sep 8  ›  │
│ │ ▤ lease-old.pdf Mar 2  ›  │
│ NOTES (1)                   │
│ │ ✎ Landlord contact     ›  │
│ CLIPS (1)                   │
│ │ ▣ Agent number  [ COPY ]  │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Search covers filenames, folder names, note titles and bodies, clip titles and contents,
link titles and URLs. Hidden clips are searchable by title only — their content is not
matched and never appears in a result snippet.

### 3.13 Upload progress panel

**Purpose:** know what is uploading without being trapped watching it.
**On it:** a panel docked above the bottom bar (mobile) or bottom-right (desktop). One row
per file: name, size, progress bar, ✓ or ✕. A header with "Uploading 2 of 5" and a
collapse chevron.
**Primary:** none — it is passive. **Secondary:** Retry on a failed row, ✕ to cancel one,
Dismiss when all are done.
**Behaviour:** navigation continues freely while it runs; it survives moving between
screens. It auto-dismisses a few seconds after everything succeeds, and stays put if
anything failed.
**Empty state:** n/a.

```
┌─────────────────────────────┐
│            …                │
│ ┌─────────────────────────┐ │
│ │ Uploading 2 of 5     ⌄  │ │
│ │ IMG_0421.jpg      ✓     │ │
│ │ IMG_0422.jpg  ████▌ 62% │ │
│ │ scan.pdf      waiting   │ │
│ │ big.zip    ✕ Too large  │ │
│ │                  Retry  │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

Errors are specific and human: *"Too large (max 2 GB)"*, *"Connection lost"*, *"Vault
disk full"*. Never a status code.

Uploads are **not resumable** in v1. Each file is streamed to disk in chunks, so a 2 GB
upload never sits in memory, but a connection dropped halfway means the partial file is
discarded and the row offers **Retry**, which starts that file again. Resumable/chunked
uploads are in `docs/BACKLOG.md` — they need an upload-session table and client-side state,
which is a stage of its own, and on a home network a retry is usually the cheaper answer.

### 3.14 Settings / About

**Purpose:** the few things worth changing, and enough to debug a bad day.
**On it:** Change password; storage used and free; item counts; vault version; last backup
time; Log out. Nothing else — no theme picker, no preferences page.
**Primary:** Change password. **Secondary:** Log out.
**Empty state:** n/a.

```
┌─────────────────────────────┐
│ Settings                    │
├─────────────────────────────┤
│ VAULT                       │
│ 4.2 GB used · 180 GB free   │
│ 412 files · 38 notes        │
│ 12 clips · 9 links          │
│                             │
│ SECURITY                    │
│ ┌─────────────────────────┐ │
│ │   Change password    ›  │ │
│ └─────────────────────────┘ │
│                             │
│ ABOUT                       │
│ Version 1.0                 │
│ Last backup: Sep 11, 02:00  │
│                             │
│ ┌─────────────────────────┐ │
│ │        Log out          │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ⌂   ▤   (＋)   ▣    ⋯      │
└─────────────────────────────┘
```

---

## 4. Key flows

Tap counts assume the app is open and logged in. The phone remembers the session, so
logging in is rare.

### Phone photo → vault — 4 taps

1. Tap `＋` in the bottom bar.
2. Tap **Photo Library** (or **Camera** to shoot one now) in the phone's own sheet.
3. Select the photo(s) — one tap each.
4. Tap **Add**.
→ The upload panel appears, the app stays where it was, a toast confirms *Uploaded*. The
photo is at the top of Home's Recent and the Photos grid immediately.

### Copy Wi-Fi password on phone — 2 taps

1. Tap **Clipboard** in the bottom bar.
2. Tap **COPY** on the Wi-Fi Password row.
→ *Copied ✓*. The password was never shown on screen. If it is pinned, it is also on Home,
which makes it 2 taps from the app opening, or 1 if Home is already showing.

### Save a link from phone — 5 taps

1. Copy the URL in the browser (outside the vault).
2. Open the vault → **More** → **Links**. *(2 taps)*
3. Tap **＋ New**. *(3)*
4. Paste into the URL field. *(4)*
5. Tap **Save** — the title is optional and defaults to the hostname. *(5)*
→ Links sits in More because saving one is a weekly act, not a daily one. A one-tap share
sheet into the vault is the backlog's "Share into the vault" item, not v1.

### Find a PDF uploaded last week — 3 taps

1. Tap the magnifier on Home.
2. Type part of the name — results appear live.
3. Tap the file row → preview, with **Download** waiting.
→ If the name is forgotten: Home → **See all** on Recent, scroll. Newest-first everywhere
is what makes this work without a date filter.

### Move 5 files into a folder on desktop — 4 clicks

1. In Files, click the checkbox on the first file, then shift-click the fifth. *(2)*
2. The bottom action bar shows "5 selected". Click **Move**. *(3)*
3. Pick the destination folder in the picker and click **Move here**. *(4)*
→ Toast: *Moved 5 files to Documents*. Drag-and-drop onto a folder row also works on
desktop, but the checkbox path is the one that has to exist — drag is a bonus, never the
only way.

---

## 5. Interaction patterns

These are the same everywhere. A pattern decided here is not re-decided per screen.

**More-actions menu.** Touch: a bottom sheet sliding up from the bottom, each action a
full-width 48px row with an icon and a label, a Cancel row at the end, tap-outside to
dismiss. Pointer: a small popover anchored to the ⋯ button. Same actions, same order, same
labels in both. Destructive actions sit last and are visually distinct.

**Confirmations.** Only for delete. One dialog, naming the thing: *"Delete passport.pdf?
This cannot be undone."* with Cancel and Delete. Everything else — rename, move, favourite,
hide, reorder — happens immediately with a toast, because it is reversible by doing it
again. Deleting a non-empty folder says how much is inside: *"Delete 'Tax 2025' and the 12
items in it?"*

**Toasts.** Bottom of the screen, above the tab bar, two seconds, one line, never stacked —
a new one replaces the old. *Copied ✓* · *Uploaded* · *Deleted* · *Moved to Documents* ·
*Renamed*. A toast never carries the only copy of important information, and never asks a
question.

**Loading.** Nothing spins for under 300ms. Past that: skeleton rows in lists, a quiet
spinner in previews. Never a full-screen blocking overlay. Lists that are already showing
data keep showing it while they refresh.

**Errors.** Plain sentences with a way forward. *"Could not save. Check your connection —
your note is still here."* Never a status code, never a stack trace, never a raw exception.
Saving a note that fails keeps the text in the box and retries in the background.

**Offline / vault unreachable.** A persistent banner: *"Can't reach the vault. Is Tailscale
connected?"* — the single most likely cause, named. Read-only screens keep showing what
they last had. The note editor keeps the text.

**Hidden clipboard items.** Content shows as `••••••`. The eye reveals it while the screen
is open; leaving and returning re-hides it. COPY always works without revealing. Hidden
content never appears in search results, never in a toast, and never in a log.

**Touch targets and forms.** Every tappable thing is at least 44×44px with at least 8px
between neighbours. Every input is at least 16px so iPhone Safari does not zoom on focus.
The bottom bar respects the safe-area inset. Primary actions sit in the bottom half of the
screen where a thumb reaches.

**Dates.** Relative for the last week (*2 hours ago*, *Yesterday*), then absolute (*Sep 10*,
and *Mar 2, 2024* once the year differs).

**Copy affordances beyond Clipboard.** Note body, link URL, filename and any text preview
each get a small Copy button. Same toast, same feedback.

---

## 6. Deliberately not in v1

Not because they are bad — because each one costs a stage and none of them serve the three
daily tasks.

- **No trash.** Delete is immediate, with a confirm. Restore is backup's job. (Backlog:
  trash with 30-day restore.)
- **No home-screen install (PWA)** and **no share-target integration**. The vault is a
  browser tab in v1. Both are in the backlog and both are worth doing later.
- **No Markdown rendering.** Notes are plain text. Rendering means a sanitiser, which means
  a dependency and a new class of bug.
- **No rich text, no tags, no colours, no folder icons, no sorting by custom order.**
- **No sharing of any kind** — no public links, no expiring links, no per-item passwords.
  Anyone on my tailnet with the password sees everything; that is the whole model.
- **No multi-user, roles, or permissions.** Stated in `CLAUDE.md` and restated here because
  it is the assumption every screen above rests on.
- **No theme switcher.** One palette, decided in D2, working in light and dark.
- **No bulk edit beyond move / download / delete.**
- **No maps, no EXIF browsing, no face grouping, no albums.** Photos is a grid by month.
- **No fulltext search index (FTS5).** A simple LIKE query over a personal vault is fast
  enough; the backlog has FTS5 for when it is not.
- **No offline editing or sync.** The vault is reachable or it is not.
- **No encryption at rest.** Files are stored as plain bytes on disk and the database is a
  plain SQLite file. This is a deliberate decision, not an oversight: full-disk encryption
  on the office computer is the right layer for it. Encrypting inside the app would mean
  the password decrypts the data, so changing it would re-encrypt everything, previews and
  thumbnails would need decryption on every request, and a lost password would mean lost
  files with no recovery. The vault's job is to keep the data behind a login and off the
  public internet; the disk's job is to protect it if the machine is stolen.
- **No video thumbnails.** Videos show an icon with a play badge. Generating real ones
  needs ffmpeg in the image. (Backlog.)
- **No resumable uploads.** A failed upload is retried from the start. (Backlog.)

---

## Answered — decisions recorded

D1's three open questions, settled on 2026-09-12. Each is folded into the sections above;
they are restated here so the reasoning is not lost.

1. **Video thumbnails: no.** No ffmpeg in v1. Videos show a video icon with a play badge in
   the Photos grid and play in the browser's own player on the preview screen. (§3.4, §3.5;
   backlogged.)
2. **Encryption at rest: no.** Files stay unencrypted on disk; full-disk encryption on the
   host is the right layer. Recorded in §6 with the reasoning, so a future session does not
   mistake it for something that was missed.
3. **Clip length: long text allowed**, capped at about 100 KB. Rows show a 2–3 line preview
   that fades out; the full text lives in a full-screen editor; COPY always copies
   everything. (§3.9.)

Two more, decided at the same time:

4. **Uploads are not resumable.** Stream to disk in chunks, show the error with Retry on
   failure. (§3.13; backlogged.)
5. **iPhone-specific work is out, but three things that look iPhone-specific are not.** The
   non-HTTPS clipboard fallback (§3.9) stays — any browser on a plain-HTTP origin refuses
   the Clipboard API, and it is the failure mode that would quietly break task 1. EXIF
   rotation on thumbnails (§3.5) stays — Android cameras record orientation as a tag too.
   HTTP Range responses (§3.4) stay — every browser needs them to seek a video. Only HEIC
   thumbnails are genuinely iPhone-only, and that is backlogged.
