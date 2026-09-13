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

---

# Part 2: Visual system

Decided in stage D2. The tokens live in `static/css/tokens.css`; this part says what they
mean and how components use them. Nothing here is a component library — it is the set of
decisions S1 turns into real CSS, so that every later stage has something to copy.

---

## 1. The direction: Paper & Ink

Three directions were considered: **Paper & Ink**, **Slate Terminal** (dark-first,
monospace, amber), and **Quiet Grey** (grey ground, white grouped cards, blue accent).

**Paper & Ink** was chosen. Warm off-white paper, near-black ink, one deep green accent,
and separation by hairline rules rather than by cards and shadows.

Why it fits this app specifically:

- **It has one loud element, and that element is COPY.** If everything is a rounded white
  card with a soft shadow, nothing stands out and the COPY button has to shout to be
  found. On paper, a single filled green slab is the only heavy thing on the screen — it is
  unmissable while the page stays calm. The visual system is built around the app's most
  frequent action.
- **Hairlines survive 375px.** Cards cost 16px of padding and 12px of gap per item. Rules
  cost one pixel. On a phone that is the difference between four clips visible and seven.
- **Warm paper is easier at both ends of the day.** This is opened at 7am and at midnight.
  Pure white glares; warm off-white does not. The dark scheme keeps the warmth rather than
  flipping to blue-black.
- **It is not the generic AI-app look.** No purple-blue gradient, no glassmorphism, no
  identical soft-shadow cards, no emoji standing in for icons, no ALL-CAPS eyebrow above
  every heading. It should read as a tool someone made on purpose.
- **It ages.** System fonts, flat colour, no effects. Nothing here looks dated in 2029 or
  breaks when a browser changes how it renders a backdrop filter.

Slate Terminal was the runner-up and is a better *night* design, but its monospace-first
treatment makes ordinary things — a note, a folder of receipts — feel more technical than
they are. Quiet Grey is the safest and the most anonymous; it would have given the vault no
character at all.

---

## 2. Colour

### 2.1 Roles

| Role | Token | Light | Dark |
|---|---|---|---|
| Page ground | `--c-bg` | `#FAF9F5` | `#151412` |
| Surface (rows, sheets) | `--c-surface` | `#FFFFFF` | `#1D1C19` |
| Raised surface (floating) | `--c-surface-raised` | `#FFFFFF` | `#24231F` |
| Sunken (code, previews) | `--c-surface-sunken` | `#F2F0E9` | `#111110` |
| Hairline | `--c-border` | `#E4E1D8` | `#302E29` |
| Strong border (inputs) | `--c-border-strong` | `#CFCABB` | `#46433C` |
| Text primary | `--c-text` | `#1A1A18` | `#F2F0E9` |
| Text secondary | `--c-text-secondary` | `#4A4944` | `#C4C0B5` |
| Text muted | `--c-text-muted` | `#6B6A63` | `#948F83` |
| Accent | `--c-accent` | `#2F6F4E` | `#5FB489` |
| Text on accent | `--c-on-accent` | `#FFFFFF` | `#0F1A14` |
| Success | `--c-success` | `#2F6F4E` | `#5FB489` |
| Danger | `--c-danger` | `#A33A2A` | `#E0705C` |
| Focus ring | `--c-focus` | `#2F6F4E` | `#5FB489` |

### 2.2 Rules for using them

- **The accent is rationed.** COPY buttons, primary buttons, links, the active tab, the
  focus ring, the pin indicator. Nothing else is green. The moment a second thing goes
  green, COPY stops being the loudest element and the whole direction collapses.
- **Success is the same green as the accent, deliberately.** "Copied ✓" should read as the
  button confirming itself, not as a new colour arriving.
- **Danger appears only on delete**, and only at the moment of deleting — a delete row in a
  sheet, the confirm button in its dialog. A file row does not turn red for having a delete
  action available.
- **Dark mode is `prefers-color-scheme` only.** No switcher (Part 1 §6).
- **The photo viewer is dark in both schemes** (`--c-viewer-bg`). An image is judged
  against a neutral dark ground, not against warm paper.

### 2.3 Contrast

Every pair below was computed, not estimated. WCAG AA needs 4.5:1 for body text and 3:1 for
focus indicators.

| Pair | Light | Dark |
|---|---|---|
| text / bg | 16.5:1 | 16.1:1 |
| text-secondary / bg | 8.6:1 | 10.1:1 |
| text-muted / bg | 5.2:1 | 5.7:1 |
| text-muted / surface | 5.4:1 | 5.3:1 |
| accent as text / bg | 5.7:1 | 7.3:1 |
| on-accent / accent | 6.0:1 | 7.1:1 |
| danger as text / bg | 6.2:1 | 5.8:1 |
| on-danger / danger | 6.6:1 | 5.7:1 |
| focus ring / bg | 5.7:1 | 7.3:1 |

`--c-text-muted` is the floor of the system — it clears AA with room to spare, so nothing
lighter than it is ever used for text. Hairlines are decoration, not information, and are
exempt.

---

## 3. Typography

**System stacks, no web fonts.** `--font-sans` resolves to San Francisco, Roboto or Segoe
depending on the device. This is not a compromise: it means zero font bytes, zero external
requests (which `CLAUDE.md` forbids anyway), no flash of unstyled text, and a vault that
renders instantly with no network at all.

**`--font-mono` carries the data** — clip contents, URLs, file sizes, hashes. An SSH key has
to be legible character by character, and `l` must not look like `1`.

| Token | Size | Used for |
|---|---|---|
| `--fs-xs` | 12px | timestamps, file sizes, counts |
| `--fs-sm` | 14px | secondary row line, labels |
| `--fs-base` | 16px | body, row titles, **every input** |
| `--fs-lg` | 18px | section headings |
| `--fs-xl` | 22px | screen title |
| `--fs-2xl` | 28px | login wordmark, large empty states |

Weights: 400 body · 500 row titles and tab labels · 600 buttons and screen titles · 700
login wordmark only. Line heights: 1.25 tight (rows, headings), 1.5 normal (body), 1.6
relaxed (note body and clip content, where long text is actually read).

**16px is a hard floor for anything typed into.** iOS Safari zooms the viewport when a
focused input is smaller, which throws the layout sideways mid-typing. Even though there is
no iPhone here (`docs/PROGRESS.md` → Environment), the rule costs nothing and the vault may
outlive the phone.

---

## 4. Space, radius, borders, shadow

**Spacing** is a 4px scale, `--space-1` … `--space-12`. `--space-4` (16px) is the default
screen gutter and the default gap between unrelated blocks.

**Radius tracks hierarchy** — small controls are nearly square, floating surfaces are soft:

| Token | Value | Applied to |
|---|---|---|
| `--radius-xs` | 3px | chips, badges, pin dot |
| `--radius-sm` | 6px | buttons, inputs, **COPY** |
| `--radius-md` | 10px | photo tiles, thumbnails, preview boxes |
| `--radius-lg` | 16px | bottom sheet, modal, upload panel |
| `--radius-full` | 999px | the ＋ button, filter pills |

**Borders do the work shadows usually do.** One hairline weight, `--c-border`. Inputs get
`--c-border-strong` so a field reads as a field when empty.

**Shadows are reserved for things that genuinely float**: the ＋ button, bottom sheets,
modals, toasts, the upload panel. A list row, a file row and a photo tile have **no shadow,
ever** — that is the single rule that keeps this from turning into the generic card look.

---

## 5. Touch and layout rules

- Every interactive target is at least **44×44px** (`--tap-min`), with at least 8px between
  neighbours. A 24px icon lives inside a 44px button; the icon is what you see, the button
  is what you hit.
- List rows are at least **56px** tall (`--row-min-height`) — two lines of text fit without
  crowding.
- The COPY button is **48px** tall and full row width.
- The ＋ button is **56px**, circular, with `--shadow-raised`.
- Anything fixed to the bottom — tab bar, upload panel, toast, sheet — adds
  `--safe-bottom` (`env(safe-area-inset-bottom)`) to its bottom padding.
- Primary actions sit in the **lower half** of the screen, where a thumb reaches.
- Content is capped at `--content-max-width` (880px) on desktop so lines stay readable.
- One breakpoint: **900px**. Below it, bottom tab bar; above it, sidebar.

---

## 6. Icons

**Lucide**, ISC licensed, vendored into `static/icons/` with its `LICENSE` file. Nothing is
fetched at runtime. 24×24, 2px stroke, round caps and joins, `stroke="currentColor"` so an
icon inherits the colour of whatever it sits in.

Icons are never emoji, and never the only label for a destructive action.

The 31 icons in the set:

| Icon | Used for |
|---|---|
| `house` | Home tab |
| `folder` · `folder-plus` · `folder-input` | folders, new folder, move to folder |
| `file` · `file-text` | generic file, text/PDF file |
| `image` · `video` · `play` | photo rows, video rows, the video play badge |
| `clipboard` | Clipboard tab |
| `link` | Links |
| `star` | favourite / pin (outline = off, filled = on) |
| `search` | search field and header magnifier |
| `plus` | the ＋ upload button, "New" buttons |
| `upload` · `download` | upload actions, download button |
| `ellipsis` | the ⋯ more-actions button |
| `chevron-left` · `chevron-right` · `chevron-down` | back, row affordance, collapse |
| `x` | close, clear search, cancel an upload |
| `check` | "Copied ✓", success rows, selection ticks |
| `copy` | copy affordances outside the Clipboard screen |
| `eye` · `eye-off` | reveal / hide a masked clip |
| `trash` | delete |
| `pencil` | rename, edit |
| `settings` | Settings |
| `log-out` | log out |
| `circle-alert` | errors, the offline banner |
| `loader-circle` | the only spinner in the app |

---

## 7. Motion

Motion exists only to confirm something the user just did. Nothing animates on load,
nothing loops, nothing bounces, nothing slides in to be decorative.

| Duration | Token | Used by |
|---|---|---|
| 120ms | `--motion-fast` | button press, star toggle, reveal a clip |
| 180ms | `--motion-base` | toast in and out, fades |
| 240ms | `--motion-sheet` | bottom sheet and modal open/close |

`prefers-reduced-motion: reduce` collapses all three to 1ms — durations shrink rather than
transitions being removed, so any code waiting on `transitionend` still fires.

The `loader-circle` spinner is the one exception that moves on its own, and it only appears
after 300ms of actual waiting.

---

## 8. Components

States are **default / hover / pressed / focus / disabled**. Hover applies to pointer
devices only (`@media (hover: hover)`) — on touch, a hover style that sticks after a tap
looks like a bug.

**Focus is the same everywhere and is never removed:** a 2px `--c-focus` ring at 2px offset,
via `:focus-visible`, so it appears for keyboard and not for mouse clicks. On accent-filled
targets the ring switches to `--c-focus-on-accent` to stay visible against green.

### 8.1 COPY button — the signature element

The one element the whole design is arranged around.

- **Default:** full row width, 48px tall, `--radius-sm`, filled `--c-accent`,
  `--c-on-accent` label, `--fw-semibold`, letter-spacing slightly open. The word COPY, not
  an icon. No shadow — it is heavy by colour, not by elevation.
- **Hover:** `--c-accent-hover`.
- **Pressed:** `--c-accent-pressed`, scale 0.99 over `--motion-fast`. A small, physical
  acknowledgement — the tap lands before the toast does.
- **Focus:** ink ring (`--c-focus-on-accent`), 2px, 2px offset.
- **Copied:** for **1.5s** the label becomes `check` + "Copied ✓" and the fill holds
  `--c-success`. The button is not disabled during this — a second copy is allowed. After
  1.5s it returns to COPY with a `--motion-base` fade.
- **Disabled:** never. A clip always has content to copy; there is no empty state for this
  button.
- **Fallback (no Clipboard API, i.e. plain HTTP):** the label reads "Select to copy", the
  fill drops to an outline in `--c-accent`, and tapping selects the text. Toast as in
  Part 1 §3.9.

It is obvious through **size, fill and isolation** — it is the only filled element in the
row — not through brightness. That is what "obvious without being loud" means here.

### 8.2 Buttons

| Variant | Default | Hover | Pressed | Focus | Disabled |
|---|---|---|---|---|---|
| **Primary** | filled `--c-accent`, `--c-on-accent`, 44px, `--radius-sm`, 600 | `--c-accent-hover` | `--c-accent-pressed`, scale .99 | ink ring | 40% opacity, `not-allowed`, no hover |
| **Secondary** | `--c-surface` + hairline, `--c-text` | `--c-surface-sunken` | `--c-surface-sunken`, border `--c-border-strong` | accent ring | 40% opacity |
| **Ghost** | transparent, `--c-text-secondary` | `--c-surface-sunken` | same, darker | accent ring | 40% opacity |
| **Danger** | `--c-danger` fill, `--c-on-danger` | `--c-danger-hover` | darker, scale .99 | ink ring | 40% opacity |

Danger is filled **only** inside a confirm dialog. In a sheet, a delete action is a normal
row with `--c-danger` text and a `trash` icon.

### 8.3 Icon button

24px icon in a 44×44px hit area, transparent ground, `--c-text-secondary`. Hover:
`--c-surface-sunken` at `--radius-sm`. Pressed: same, scale .95. Focus: accent ring.
Disabled: 40%. Every one carries an `aria-label` — there is no visible text to read.

### 8.4 Text input, textarea, search field

- **Input:** 44px tall, 16px text (never smaller), `--c-surface`, `--c-border-strong`
  hairline, `--radius-sm`, 12px horizontal padding. Placeholder `--c-text-muted`.
- **Hover:** border `--c-text-muted`. **Focus:** border `--c-accent` + 2px accent ring.
- **Disabled:** `--c-surface-sunken`, muted text.
- **Invalid:** border `--c-danger`, message below in `--c-danger` at `--fs-sm`. Never a red
  glow, never a shake.
- **Textarea:** same, min 120px, `--lh-relaxed`, vertical resize only. The note and clip
  editors use a full-height borderless variant — the screen *is* the field.
- **Search:** input with a leading `search` icon and, once typed in, a trailing `x` in its
  own 44px target. Desktop focuses on `/`; Escape clears.

### 8.5 List row and file row

- **List row:** min 56px, `--c-surface`, hairline **below only** (no box), 16px gutter.
  Title `--fs-base`/500 `--c-text`; second line `--fs-sm` `--c-text-muted`. Trailing ⋯ or
  `chevron-right`.
- **File row:** icon by type (24px, `--c-text-muted`) or a 40px `--radius-md` thumbnail ·
  filename (truncating with an ellipsis in the **middle**, so extensions stay visible) ·
  second line `size · date` in `--fs-xs` `--c-text-muted` · `star` if pinned · ⋯.
- **Hover:** `--c-surface-sunken`. **Pressed:** same, 100ms. **Focus:** inset accent ring.
- **Selected** (select mode): `--c-accent-subtle` ground, `check` in a filled accent circle
  on the left.
- **Disabled:** not a state — a row that cannot be acted on is not shown.

### 8.6 Photo tile

Square, `--radius-md`, `object-fit: cover`, `--c-surface-sunken` while loading, 3 across at
375px with `--space-1` gutters. Hover: 96% brightness. Pressed: scale .98. Focus: 2px accent
ring at 2px offset. Selected: accent ring plus a filled `check` top-right. Videos carry a
`play` badge bottom-left with duration — there is no generated thumbnail (Part 1 §3.5).

### 8.7 Bottom tab bar

56px plus `--safe-bottom`, `--c-surface`, hairline on top, no shadow. Five slots. Each tab:
24px icon over an 11px label, full height, at least 44px wide. **Inactive**
`--c-text-muted`; **active** `--c-accent` with the label at 500 — colour and weight, not a
pill or an underline. Pressed: `--c-surface-sunken`. Focus: inset accent ring.

The ＋ is not a tab: 56px circle, filled `--c-accent`, `--c-on-accent` `plus` icon,
`--shadow-raised`, centred and lifted 8px above the bar. It never shows an active state
because it is an action, not a destination.

### 8.8 Sidebar (desktop)

232px, `--c-bg` ground, hairline on the right. Items are 40px tall with a 20px icon and a
16px label, `--radius-sm`, 8px inset. Hover `--c-surface-sunken`; **active**
`--c-accent-subtle` ground with `--c-accent` icon and text at 500. A primary ＋ Upload
button sits at the top; Settings sits at the bottom, separated by a hairline.

### 8.9 Breadcrumb

`--fs-sm` `--c-text-secondary`, `chevron-right` separators in `--c-text-muted`. The last
crumb is `--c-text` at 500 and is not a link. On mobile only `‹ parent / current` is shown —
deeper paths collapse to a leading `‹`. Each crumb is a 44px-tall target.

### 8.10 Action bottom sheet

Slides from the bottom over a `--c-scrim` in `--motion-sheet` `--ease-out`.
`--c-surface-raised`, `--radius-lg` on the top corners only, `--shadow-sheet`, a 36px grab
handle, and `--safe-bottom` padding. Rows are 48px, 20px icon + 16px label, left aligned,
hairline between. Destructive rows sit last in `--c-danger`. Dismissed by tapping the scrim,
swiping down, or Escape. Focus is trapped while open and returns to the ⋯ button on close.

On pointer devices the same actions render as an anchored popover: `--c-surface-raised`,
hairline, `--radius-sm`, `--shadow-modal`, 32px rows, no grab handle.

### 8.11 Modal (confirm)

Centred, max 400px wide, `--c-surface-raised`, `--radius-lg`, `--shadow-modal`, over the
scrim. Title `--fs-lg`/600, body `--fs-base` `--c-text-secondary` naming the thing being
deleted. Buttons bottom-right on desktop, stacked full-width on mobile with the destructive
one on top. **Cancel is focused by default**, so a stray Enter cancels rather than deletes.
Escape cancels. Used for deletes only.

### 8.12 Toast

Bottom centre, above the tab bar and `--safe-bottom`. `--c-text` ground with `--c-bg` text —
inverted, so it reads as a system message rather than another card. `--radius-sm`,
`--shadow-modal`, max 320px, one line. Fades and rises 8px over `--motion-base`, holds 2s,
fades out. A new toast replaces the current one; they never stack. Success toasts carry a
`check`; error toasts use `circle-alert` in `--c-danger` and hold 4s. Rendered in an
`aria-live="polite"` region. Never carries the only copy of important information.

### 8.13 Upload progress row

Inside the panel (Part 1 §3.13): filename (middle-truncated) · size · a 4px progress track
in `--c-surface-sunken` with an `--c-accent` fill and `--radius-full`. Percentage in
`--fs-xs` `--c-text-muted`. States: **waiting** (muted text, no bar) · **uploading** (bar
advances, `x` to cancel) · **done** (`check` in `--c-success`, bar gone) · **failed**
(`circle-alert` in `--c-danger`, the reason in plain words, a **Retry** ghost button).
The panel is `--c-surface-raised`, `--radius-lg`, `--shadow-sheet`.

### 8.14 Empty state

Centred in the content area, generous top space. A 32px icon in `--c-text-muted`, one line
of `--fs-base` `--c-text-secondary` explaining what goes here, and — where there is an
obvious next step — one primary button. No illustrations, no cartoons. The copy is written
per screen in Part 1.

### 8.15 Pin indicator

A `star` icon, 20px inside a 44px target. **Off:** outline, `--c-text-muted`. **On:**
filled, `--c-accent`. Toggling animates the fill over `--motion-fast` with no bounce, and
shows no toast — the icon changing *is* the feedback.

---

## 9. What Part 2 deliberately leaves out

- No theme switcher, no accent picker, no density setting.
- No web fonts, no icon font, no CSS framework, no utility-class system. Plain CSS with
  custom properties.
- No gradients, no glassmorphism, no blur effects, no decorative illustration.
- No animation library. The handful of transitions above are written by hand.
- No component JS beyond what S1–S11 actually need; this part describes appearance and
  state, not implementation.
