# Personal Vault

A private place for your files, photos, notes, clipboard snippets and links. It runs on
your own always-on computer and you reach it from your own devices over Tailscale.
Nothing is public and nothing goes to a cloud service.

> **Status:** under construction (stage S2 — login works, no features yet).
> The full guide — installing Docker and Tailscale, phone access, backup, restore,
> troubleshooting — is written in stage S10. Progress: `docs/PROGRESS.md`.

## Start it with Docker

```bash
mkdir -p data backups                 # create these yourself, so they belong to you, not root
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # copy the output…
nano .env                             # …and paste it after SESSION_SECRET=
docker compose up -d --build
docker compose run --rm vault python -m app.cli set-password   # choose your password
```

Open <http://localhost:8000> on this computer and log in. Forgot the password? Run the
`set-password` line again: it sets a new one and logs out every device. `docker compose logs vault` shows the app's
log; `docker compose down` stops it. Your data stays in `./data` either way.

## For development (no Docker)

```bash
uv venv -p 3.12 .venv && . .venv/bin/activate
uv pip install -r requirements-dev.txt
pytest
SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))") \
  VAULT_DATA_DIR=./data VAULT_BACKUP_DIR=./backups python -m app
```
