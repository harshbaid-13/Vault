# Build a Self-Hosted Personal Vault Web App

Build a complete, production-quality but lightweight **private personal vault web application** that runs on my always-on office computer and can be accessed from my other devices through a private Tailscale network.

The goal is to create a simple personal "Dropbox + notes + clipboard" that I control.

## Core concept

My office computer is the server and stays powered on.

I want to open the vault from my phone, laptop, tablet, or another trusted device using a private URL/hostname over Tailscale.

Example:

`http://office-vault:8000`

or whatever hostname/port is appropriate.

The application must NOT require a public internet-facing server.

Do not unnecessarily expose ports to the public internet.

## Technology

Use a simple, maintainable stack:

* Backend: Python + FastAPI
* Frontend: modern responsive web UI
* Database: SQLite
* File storage: local filesystem on the office computer
* Authentication: single personal user/password
* Password hashing: Argon2id
* Private networking: Tailscale
* Deployment: Docker + Docker Compose if practical
* Reverse proxy/Caddy: NOT required for the initial version
* No cloud storage dependency

Choose sensible modern libraries and explain major choices briefly in the README.

## Main requirements

### 1. Login

Create a clean login page.

The user enters one password.

Requirements:

* Store only a secure Argon2id password hash.
* Never store the plaintext password.
* Use secure sessions/cookies.
* Include logout.
* Protect all authenticated routes.
* Do not expose files directly without authentication.
* Rate-limit repeated failed login attempts where practical.
* Use secure defaults.

For the first version, there is only one personal account.

Provide a simple way to configure/set the initial password during installation rather than hard-coding it.

## 2. Dashboard

After logging in, show a clean dashboard with:

* Recent files
* Recent notes
* Pinned items
* Upload button
* Search
* Navigation

Suggested navigation:

* Home
* Files
* Photos
* Notes
* Clipboard
* Links
* Favorites

Keep the interface visually clean, fast, and minimal.

It should feel like a personal utility rather than enterprise software.

## 3. File uploads

I need to be able to upload essentially any normal file:

* images
* videos
* PDFs
* Word documents
* spreadsheets
* text files
* ZIP files
* arbitrary other files

Support:

* drag-and-drop upload
* normal file picker
* multiple file upload
* upload progress
* filename display
* file size
* upload date
* rename
* delete
* download
* favorite/pin
* move between folders

Store files on local disk.

Use a safe filesystem structure and do not trust user-provided filenames or paths.

Prevent path traversal.

Do not store uploaded files directly using arbitrary user-controlled paths.

## 4. File browser

Create a file manager-style interface.

Show:

* filename
* type
* size
* modified/upload date
* favorite status

Allow:

* search
* sort
* folder navigation
* create folder
* rename
* move
* delete
* download

Add thumbnails/previews where practical.

For example:

* Images → image preview
* PDFs → PDF preview
* Text → text preview
* Other files → file information/download

Do not attempt unsafe execution of uploaded files.

## 5. Photos

Photos should have a more visual browsing experience.

Create a gallery view with thumbnails.

Allow:

* click to open larger preview
* next/previous navigation
* download
* rename
* delete
* favorite
* copy/share access link only within the authenticated/private system

Do not publicly expose the images.

## 6. Notes

Create a simple notes system.

Each note should support:

* title
* body
* created date
* modified date
* favorite/pin
* delete

The editor should be extremely quick to use.

Plain text is sufficient for version 1, but lightweight Markdown support is welcome.

Autosave would be useful.

## 7. Clipboard

Create a dedicated **Clipboard** section for frequently copied text.

Each clipboard item should have:

* title
* text/content
* favorite/pin
* created date
* modified date

Most importantly:

Every item should have a prominent **COPY** button.

Clicking COPY should place the item's text into the device clipboard using the browser Clipboard API.

Example:

```text
Wi-Fi Password
MySecretPassword

[ COPY ]
```

This should work especially well on mobile.

Allow:

* create
* edit
* copy
* delete
* favorite
* search

## 8. Links

Create a simple saved-links section.

Each link should have:

* title
* URL
* optional description
* created date
* favorite

Clicking the item should open the URL in a new tab.

## 9. Universal search

Add a search box available from the main interface.

Search across:

* filenames
* folders
* notes
* clipboard items
* saved links

Make search fast.

SQLite full-text search can be used if useful, but a simpler implementation is acceptable for the initial version.

## 10. Favorites / pinned items

Allow any important item to be favorited.

The Home page should show a convenient "Pinned" or "Favorites" section.

Examples:

* frequently used text
* important PDF
* useful image
* frequently used link

## 11. Mobile-first responsive design

This is very important.

I will frequently access this from my phone.

The UI should work beautifully on:

* iPhone
* Android phone
* tablet
* laptop
* desktop

Use responsive layouts.

Buttons should be large enough for touch.

The upload flow should work well on mobile.

For example, I should be able to:

1. Open the site on my phone.
2. Log in.
3. Tap Upload.
4. Select/take a photo.
5. Upload it.
6. Immediately see it in the vault.

## 12. Copy-friendly UX

Anything that is text should be easy to copy.

Examples:

* note content
* clipboard entries
* URLs
* filenames where useful

Use clear COPY buttons and provide a small visual confirmation such as:

`Copied ✓`

## 13. Security model

The application is personal, but security still matters.

Implement sensible security practices:

* Argon2id password hashing
* secure authentication/session handling
* authenticated access to every private resource
* no direct public filesystem exposure
* path traversal protection
* filename sanitization
* CSRF protection where applicable
* sensible upload limits/configuration
* validation of uploaded filenames and metadata
* safe deletion
* safe error handling
* do not leak sensitive information in errors/logs
* avoid executing uploaded files
* protect API endpoints behind authentication

Do not build unnecessary enterprise authentication.

A single strong password is enough for this personal application.

## 14. Tailscale

The application should be designed to run privately through Tailscale.

Document how to:

1. Install Tailscale on the office computer.
2. Install Tailscale on my phone/laptop.
3. Start the application.
4. Access the app through the Tailscale network.

Prefer a Tailscale hostname if available.

Do not require opening router ports.

Do not require port forwarding.

## 15. Docker

Provide:

* Dockerfile
* docker-compose.yml

The application should have persistent storage.

For example:

```text
./data/
    database/
    files/
```

Do not lose uploaded files or database contents when the container restarts.

Use volumes correctly.

The application should restart cleanly after the office computer reboots.

## 16. Backup

Create a simple backup strategy.

Document how I can back up:

* SQLite database
* uploaded files

Ideally provide a simple backup script such as:

```bash
./backup.sh
```

The backup should produce a dated backup folder/archive.

Do not require cloud backups.

## 17. Configuration

Use environment variables or a `.env` file for configuration.

Possible settings:

```text
VAULT_DATA_DIR
VAULT_DB_PATH
SESSION_SECRET
INITIAL_PASSWORD
MAX_UPLOAD_SIZE
```

Do not commit secrets into source control.

Provide `.env.example`.

## 18. Project structure

Keep the project organized and maintainable.

For example:

```text
personal-vault/
├── app/
│   ├── main.py
│   ├── auth/
│   ├── files/
│   ├── notes/
│   ├── clipboard/
│   ├── links/
│   ├── templates/
│   └── static/
├── data/
├── scripts/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── backup.sh
└── README.md
```

You may adjust the structure if you have a better architecture.

## 19. UI design

Make the UI polished.

Design goals:

* minimal
* modern
* fast
* calm
* practical
* easy to understand
* excellent mobile experience

Avoid unnecessary animations.

Use clear icons and familiar interactions.

The Home page should immediately answer:

"What did I recently upload?"

"What did I pin?"

"What can I quickly copy?"

## 20. Dashboard example

Something along these lines:

```text
┌─────────────────────────────────────────────┐
│ MY VAULT                     🔍     ＋ Upload│
├─────────────────────────────────────────────┤
│                                             │
│  📁 Files   📷 Photos   📝 Notes            │
│  📋 Clipboard   🔗 Links                   │
│                                             │
│  Pinned                                     │
│  ─────────────────────────────────────────  │
│  Wi-Fi Password                  [COPY]     │
│  passport.pdf                    [VIEW]     │
│                                             │
│  Recent                                     │
│  ─────────────────────────────────────────  │
│  vacation.jpg                   Sep 10      │
│  project.pdf                    Sep 10      │
│  shopping-list.txt              Sep 9       │
│                                             │
└─────────────────────────────────────────────┘
```

## 21. API

Create clean backend APIs for:

* authentication
* files
* folders
* uploads
* downloads
* previews
* notes
* clipboard
* links
* favorites
* search

Use proper HTTP methods and validation.

## 22. Testing

Include useful automated tests.

At minimum test:

* authentication
* incorrect password
* authenticated access
* unauthenticated access rejection
* file upload
* file download
* filename/path traversal protection
* file deletion
* note CRUD
* clipboard CRUD
* search

## 23. README

Provide a very clear README written for a non-developer.

It should explain:

### Installation

How to install Docker and Tailscale if necessary.

### Start

Something simple like:

```bash
docker compose up -d
```

### Create password

Explain how to configure the first password securely.

### Access

Explain how to find the Tailscale address/hostname.

### Updating

Explain how to update/rebuild the app.

### Backup

Explain how to back up the vault.

### Restore

Explain how to restore it.

### Troubleshooting

Include common problems and solutions.

## 24. Important implementation preference

Do not over-engineer this.

This is a **personal utility**, not a SaaS platform.

Prefer:

* simple architecture
* few dependencies
* easy maintenance
* predictable behavior
* strong security basics
* excellent UX

Avoid adding:

* multi-tenant architecture
* complicated permissions
* social features
* public sharing
* unnecessary cloud services
* unnecessary microservices

## 25. Deliverable

Produce the complete working project.

Do not stop at a prototype or pseudocode.

I should be able to clone/copy the project onto my office computer, configure the password, run Docker Compose, connect through Tailscale, and use the application from my other devices.

Before finishing:

1. Run the tests.
2. Check that the application starts successfully.
3. Check authentication.
4. Check uploading/downloading.
5. Check mobile responsiveness as far as practical.
6. Fix obvious errors.
7. Provide the final project structure and setup instructions.

Make sensible decisions without repeatedly asking me for approval.

The priority order is:

**security → reliability → simplicity → excellent everyday usability → visual polish**
