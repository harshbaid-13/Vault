# Personal Vault

A private place for your files, photos, notes, clipboard snippets and links. It runs on your
office computer and you open it from your own phone and laptop over Tailscale. Nothing is
public, nothing goes to a cloud service, and there is one password: yours.

- **Clipboard:** text you copy often (Wi-Fi password, address, UPI ID) with a one-tap COPY.
- **Files and Photos:** upload from the phone or laptop (up to 2 GB each), folders, previews.
- **Notes and Links:** plain notes that save as you type; links that open in one tap.
- **Home, Favorites, Search:** your starred things, what arrived recently, and one search box.

Everything below is typed in a terminal on the **office computer** (Ubuntu 26.04), inside the
`personal-vault` folder unless it says otherwise.

---

## Security model and threat assumptions

Read this before you run it. The vault is built for one specific situation, and it is only
safe inside that situation.

**What it assumes**

- **One person, one password.** There are no accounts, roles or permissions, and there never
  will be. Anyone who knows the password is you.
- **Your tailnet is the security boundary.** The app trusts every device that can reach it.
  Tailscale — not the app — is what keeps strangers out.
- **The office computer is trusted.** Files, the database and backups are stored unencrypted
  on its disk. Anyone with an account on that machine, or with the disk in their hand, has
  everything. Use full-disk encryption if that matters to you.

**Never do these**

- **Do not run `tailscale funnel`.** That publishes the vault to the whole internet.
- **Do not forward a port** on your router to port 8000.
- **Do not put it behind a public reverse proxy** (nginx, Caddy, Cloudflare Tunnel, ngrok).
- **Do not change the bind address** to `0.0.0.0` on the host. `docker-compose.yml` publishes
  on `127.0.0.1:8000` on purpose; `tailscale serve` is what reaches out to your devices.

One password with no second factor is fine on a private tailnet. It is not fine on the open
internet, and this app does not pretend otherwise.

**What the app does do**

- Login is required on **every** route by default. Only `/login`, `/static` and `/healthz` are
  public — a new route is protected without anyone remembering to protect it.
- The password is stored only as an **Argon2id** hash. After five wrong attempts, logging in
  locks for 60 seconds, doubling with each further miss up to 15 minutes. Changing the
  password logs out every other device.
- Writes must come from the vault's own pages (an `Origin`/`Referer` check), so another site
  open in the same browser cannot act on your vault.
- Uploaded HTML, SVG, XML and JS are **never** shown inline — they download, with a sandbox
  CSP and `nosniff`, so an uploaded file cannot run script as your vault.
- A file name you type is display text only. Bytes on disk are named by a generated UUID, so
  a name like `../../etc/passwd` is just a name.
- The logs record ids and counts only — never a password, note, clipboard entry, file name or
  search term. The web-server access log is switched off for the same reason.

**What it deliberately does not do**

- **No encryption at rest.** `data/` and `backups/` are ordinary files.
- **Sessions are signed cookies.** Logging out clears the cookie in that browser, but a cookie
  copied off a device stays valid until it expires (30 days). To log out *everywhere*, change
  the password.
- **The login lockout is one global counter**, because behind `tailscale serve` every request
  arrives from the same address. Someone already on your tailnet can therefore lock *you* out
  for up to 15 minutes by guessing wrong. That is the intended trade: a stranger who somehow
  reaches the login page cannot brute-force it.
- **No audit log, no intrusion detection, no rate limit** on anything but login.

**Found a problem?** Open a GitHub issue for anything routine. For something that would let
someone else read a vault's contents, please report it privately through GitHub's *Security →
Report a vulnerability* instead of opening a public issue.

---

## 1. Install Docker and Tailscale (once)

### Docker

These steps are Docker's own, from <https://docs.docker.com/engine/install/ubuntu/>
(checked 2026-09-18; Ubuntu 26.04 "Resolute" is supported). If a line fails, check that page.

```bash
# Remove old packages that conflict (fine if it says none are installed)
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc | cut -f1)

# Add Docker's package source
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update

# Install Docker and the compose plugin
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Check it works
sudo docker run hello-world
```

Then let your own user run `docker` without `sudo` (needed by the nightly backup), and make
Docker start when the computer boots — otherwise the vault is gone after a power cut:

```bash
sudo groupadd docker          # "already exists" is fine
sudo usermod -aG docker $USER
newgrp docker                 # or log out and back in
docker run hello-world        # now without sudo

sudo systemctl enable docker.service
sudo systemctl enable containerd.service
```

Docker's docs warn that the `docker` group is as powerful as root. On a computer only you use,
that's the normal setup.

### Tailscale

Follow **[docs/TAILSCALE.md](docs/TAILSCALE.md)** steps 1–3: install it on the office
computer, your phone and your laptop, and turn on HTTPS. Do step 4 onwards after the vault is
running (section 3 below).

---

## 2. First-time setup

```bash
git clone <this repository> personal-vault      # or copy the folder over
cd personal-vault
mkdir -p data backups       # create these yourself, so they belong to you and not to root
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the long line that last command printed. Open the settings file with `nano .env`, paste
it after `SESSION_SECRET=` (replacing the example text), then save with **Ctrl+O, Enter** and
quit with **Ctrl+X**. The vault refuses to start until you do this. Never share or commit
`.env`.

Build and start the vault, then choose your password:

```bash
docker compose up -d --build
docker compose run --rm vault python -m app.cli set-password
```

It asks twice and shows nothing while you type. Only a secure hash of it is stored.

## 3. Start, stop, check

```bash
docker compose up -d          # start (it also starts by itself after a reboot)
docker compose ps             # should say "healthy" after a few seconds
docker compose logs vault     # the app's log (ids and counts only — never your content)
docker compose down           # stop. Your data stays in ./data
```

On the office computer itself, open <http://localhost:8000>.

## 4. Open it from your phone and laptop

Do steps 4–6 of **[docs/TAILSCALE.md](docs/TAILSCALE.md)**. You get an address like
`https://office-vault.tail1234.ts.net` that works only on your own devices. Bookmark it on
the phone (or "Add to Home screen"). Settings in the vault shows **HTTPS: Yes ✓** when it's
right; that's also what makes COPY work in one tap.

To find the address later: `tailscale serve status` on the office computer.

## 5. Change the password

In the vault: **Settings → Change password** (needs the current one). Other devices are
logged out; this one stays in.

**Forgot it?** On the office computer:

```bash
docker compose run --rm vault python -m app.cli set-password
```

That sets a new one and logs out every device.

## 6. Update to a new version

Back up first, then:

```bash
./backup.sh
git pull
docker compose up -d --build
docker compose ps             # "healthy" again
```

Your data is untouched; any database changes are applied automatically at start. Settings
shows the version.

---

## 7. Backup

`./backup.sh` backs up the **running** vault into `./backups` — safe while you use it:

```text
backups/
├── db/vault-2026-09-18_0230.db     one checked copy of the database per run (newest 30 kept)
└── files-mirror/…                   every uploaded file, copied once and checked against its fingerprint
```

Files never change after upload, so each run copies only what's new, and every snapshot
costs only the size of the database (a few MB). It prints what it did and ends with
`Backup done`. If anything is missing it says `Backup INCOMPLETE`, keeps that snapshot
marked `-INCOMPLETE`, and exits with an error.

### Every night, automatically (cron)

```bash
crontab -e
```

(Pick `nano` if asked.) Add this line at the bottom, with your own folder, then save:

```text
30 2 * * * $HOME/personal-vault/backup.sh >> $HOME/personal-vault/backups/backup.log 2>&1
```

That runs at 02:30 every night. The office computer must be on (not asleep) at that time.
Check it the next day: `tail backups/backup.log` should end in `Backup done`, and the
vault's **Settings → Last backup** shows the time.

### Every week: copy it off this computer

A backup on the same disk doesn't survive that disk dying. Plug in an external drive and:

```bash
rsync -a --info=progress2 ~/personal-vault/backups/ /media/$USER/<your-drive>/vault-backups/
```

`<your-drive>` is the drive's name (`ls /media/$USER` shows it). rsync copies only what's new,
so after the first time this is quick. It never deletes anything on the drive. Keep the drive
somewhere other than next to the computer.

### Every month: check the backup can be read

```bash
./backup.sh --verify
```

It re-reads every backed-up file and checks it against its fingerprint (slow for big vaults).
`Verify OK` is what you want. If a file is damaged, copy it back from the external drive.

### Freeing space in the backups

Files you delete in the vault stay in `backups/files-mirror` as long as any kept snapshot
still lists them (that's what lets a restore bring them back). Once they're older than every
kept snapshot, remove them with:

```bash
./backup.sh --prune-mirror
```

### Check the vault's files

```bash
docker compose exec vault python -m app.cli check
```

It compares the database with what's on disk: `Everything matches.` is what you want. It can
report **orphans** (bytes with no entry — what a power cut in the middle of a delete leaves
behind; `check --fix` deletes them) and **MISSING** files (an entry whose bytes are gone —
restore those from a backup, section 8). Nothing is deleted unless you pass `--fix`.

## 8. Restore

This puts the vault back exactly as it was at one backup. It checks everything first and
changes nothing if the backup is incomplete. Your current data is **moved aside, never
deleted**.

```bash
docker compose down
docker compose run --rm vault python -m app.restore           # lists the snapshots
docker compose run --rm vault python -m app.restore vault-2026-09-18_0230.db
docker compose up -d
```

When it finishes it tells you where the old data went, e.g. `data/before-restore-2026-09-18_101500/`.
Check the vault in the browser; once you're happy, delete that folder to get the space back:
`rm -r data/before-restore-2026-09-18_101500`.

**On a new computer:** set up Docker, Tailscale and `.env` as above, copy your `backups`
folder (from the external drive) into `personal-vault/`, then run the restore commands. Use
the same password as before — it's inside the backup.

---

## 9. Troubleshooting

| Problem | What to do |
|---|---|
| **COPY doesn't copy**, or says "Press and hold to copy" | You opened the vault over plain `http://`. Use the `https://….ts.net` address (Settings shows **HTTPS: Yes ✓**). See docs/TAILSCALE.md. |
| **Can't reach the vault from the phone** | Tailscale must be switched on on **both** the phone and the office computer (`tailscale status` lists your devices). The office computer must be awake. `tailscale serve status` should show port 8000. More in docs/TAILSCALE.md → "When it doesn't work". |
| **Login keeps failing / "Too many attempts"** | After 5 wrong passwords the login waits 60 seconds, then twice as long after each further wrong try (up to 15 minutes), even for the right password. Wait it out, or restart the vault to clear it: `docker compose restart`. Forgot the password? See section 5. |
| **Big uploads fail** | The limit is `MAX_UPLOAD_SIZE_MB` in `.env` (2048 = 2 GB). Change it, then `docker compose up -d`. If large files fail only from the phone or laptop but work at `http://localhost:8000`, the Tailscale connection is the limit: try on Wi-Fi, or lower the limit. |
| **"Vault disk full"** | The vault keeps 512 MB free on its disk. `df -h .` shows space. Delete big files you don't need, remove old `data/before-restore-*` folders, and if backups are on the same disk, run `./backup.sh --prune-mirror`. |
| **Vault not running after a reboot** | `systemctl is-enabled docker` must say `enabled` (see section 1). Then `docker compose ps`; if it isn't listed, `docker compose up -d`. |
| **"database is locked"** in the log | Something else has `data/vault.db` open — a database viewer, or a restore run while the vault was up. Close it, then `docker compose restart`. Never copy `vault.db` by hand; use `./backup.sh`. |
| **Backup says `permission denied` or can't talk to Docker** | Your user isn't in the `docker` group yet: run the `usermod` line in section 1 and log out and in. |
| **Backup INCOMPLETE** | It lists the file ids it couldn't copy. Usually a file missing from `data/files` (disk trouble). The next backup tries again; the earlier complete snapshots are still good. |
| **Forgot the password** | `docker compose run --rm vault python -m app.cli set-password` (logs every device out). |
| **The vault won't start and the log says SESSION_SECRET** | `.env` still has the example value or is missing. Redo section 2. |
| **A file won't open, or the vault seems to have lost one** | `docker compose exec vault python -m app.cli check` says whether the file's bytes are missing (restore, section 8) or whether there are leftovers to clean up (`check --fix`). |
| **Anything else** | `docker compose logs vault --tail 50` shows what happened. |

---

## 10. Project structure

```text
personal-vault/
├── README.md             this guide
├── docker-compose.yml    the one service; ./data and ./backups mounted; port 8000 on this computer only
├── Dockerfile            Python 3.12 image, runs as your user (uid 1000)
├── .env.example          settings to copy into .env (secrets live only in .env)
├── backup.sh             ./backup.sh → python -m app.backup inside the container
├── scripts/seed_demo.py  fills a throw-away vault with demo content, to test how it behaves when full
├── app/                  the web app: one Python module per feature (clips, notes, links, files,
│   │                     folders, photos, home), plus login, storage, thumbnails, backup, restore
│   ├── migrations/       the database layout
│   └── templates/        the pages (HTML)
├── static/               CSS, JavaScript and icons — everything the browser needs, nothing from the internet
├── tests/                automatic checks (pytest)
├── docs/                 design, technical plan, progress, Tailscale guide, ideas for later
├── data/                 YOUR VAULT: database, files, thumbnails (not in git)
└── backups/              snapshots and the files mirror (not in git)
```

## 11. Why these technologies

- **Python + FastAPI**, pages made on the server with **Jinja2**: small, readable, and no
  JavaScript build tools to keep up to date. The little JavaScript there is is one plain file.
- **SQLite**: the whole database is one file, needs no server, and has a built-in safe way to
  copy it while in use — which is what the backup relies on.
- **Files on disk under random names**, never under the names you gave them, so a strange file
  name can't do anything harmful. Names live in the database.
- **Docker**: one command to start, the same on any computer, and it restarts by itself.
- **Tailscale**: your devices reach the vault over an encrypted private network with a real
  HTTPS certificate, and nothing is opened to the internet.
- **Argon2id** for the password hash: the current recommended way to store a password.

---

## For development (no Docker)

Only needed if you want to run the tests or the app without Docker. Python 3.12 and `pip` are
enough — nothing else to install:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))") \
  VAULT_DATA_DIR=./data VAULT_BACKUP_DIR=./backups python -m app
```

If you have [uv](https://docs.astral.sh/uv/), `uv venv -p 3.12 .venv` and
`uv pip install -r requirements-dev.txt` do the same thing faster. The pinned versions in
`requirements*.txt` were resolved with it, but pip installs them just as well.
