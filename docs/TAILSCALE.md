# Opening the vault from your phone and laptop (Tailscale)

Tailscale puts your office computer, phone and laptop on one private network that only your
devices can join. The vault gets a real `https://` address on that network, so copy buttons
work in one tap and your password never travels unencrypted.

Install steps below were checked against Tailscale's own docs on **2026-09-17**
(tailscale.com/kb/1031/install-linux, pkgs.tailscale.com/stable, tailscale.com/kb/1153/enabling-https,
tailscale.com/kb/1242/tailscale-serve). If a command fails, check those pages first.

**Before you start:** the vault is running on the office computer
(`docker compose ps` says `healthy`) and you have set a password.

---

## 1. Office computer (Ubuntu 26.04): install Tailscale and sign in

Open a terminal and run these four commands one at a time. They add Tailscale's official
package source for Ubuntu 26.04 ("resolute") and install it.

```bash
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/resolute.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/resolute.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt-get update && sudo apt-get install tailscale
sudo tailscale up
```

`sudo tailscale up` prints a link. Open it, sign in (Google, Microsoft, GitHub or Apple —
pick one and use **the same account on every device**), and approve the computer.

Make sure Tailscale and Docker both start by themselves after a reboot or power cut:

```bash
sudo systemctl enable --now tailscaled
sudo systemctl enable --now docker
systemctl is-enabled tailscaled docker     # should print "enabled" twice
```

Check it worked:

```bash
tailscale status      # the first line is this computer, with a 100.x.y.z address
```

## 2. Phone and laptop: install Tailscale

- **Android phone:** install **Tailscale** from the Play Store, open it, sign in with the
  same account, and turn it on. Allow the VPN prompt — Tailscale uses Android's VPN slot, but
  only traffic for your own devices goes through it.
- **Laptop:** download from <https://tailscale.com/download>, install, sign in with the same
  account.

In the office computer's terminal, `tailscale status` should now list all three devices.

## 3. Admin console: name the computer, keep it signed in, turn on HTTPS

Open <https://login.tailscale.com/admin/machines> on the laptop.

1. **Rename the office computer to `office-vault`.** Click the `⋯` next to it → **Edit
   machine name**. The name becomes part of the vault's address, and it is published in a
   public certificate log when HTTPS is turned on, so don't use a name that says anything
   private.
2. **Turn off key expiry for it.** Same `⋯` menu → **Disable key expiry**. Otherwise
   Tailscale signs the office computer out every few months and the vault silently
   disappears from your phone.

Then open the **DNS** page: <https://login.tailscale.com/admin/dns>

3. **MagicDNS:** enable it if it isn't already.
4. **HTTPS Certificates:** click **Enable HTTPS** and accept the note about machine names
   being public.

On that DNS page, note your **tailnet name** — something like `tail1234.ts.net`.
Your vault's address will be:

```text
https://office-vault.tail1234.ts.net
```

## 4. Office computer: serve the vault over HTTPS

```bash
sudo tailscale serve --bg 8000
```

This tells Tailscale: "on this computer's `https://` address, pass every request to the vault
on port 8000." `--bg` keeps it running in the background, and it comes back by itself after a
reboot. The first request can take a few seconds while the certificate is issued.

Useful commands:

| What | Command |
|---|---|
| See what is being served, and the address | `tailscale serve status` |
| Stop serving the vault | `sudo tailscale serve --https=443 off` |
| Remove every serve setting | `sudo tailscale serve reset` |

**Never use `tailscale funnel`.** Funnel puts a service on the public internet. `serve` only
reaches devices signed in to your own tailnet.

## 5. Tell the vault its new address

Edit `.env` in the vault folder (`nano .env`) and set these two lines, using **your** address
from step 3 — no slash at the end:

```text
VAULT_COOKIE_SECURE=true
VAULT_ALLOWED_ORIGINS=https://office-vault.tail1234.ts.net
```

Then restart the vault so it reads them:

```bash
docker compose up -d --force-recreate
```

- `VAULT_COOKIE_SECURE=true` makes the browser send your login cookie only over HTTPS.
- `VAULT_ALLOWED_ORIGINS` tells the vault that changes (logging in, saving, deleting) coming
  from that address are really from its own pages. Without it, logging in over the `ts.net`
  address shows *"This request didn't come from the vault's own pages"*.

On the office computer itself, <http://localhost:8000> keeps working as before.

## 6. Check it from your phone

1. Turn **Wi-Fi off** on the phone, so it uses mobile data only.
2. Make sure the Tailscale app is on.
3. Open `https://office-vault.tail1234.ts.net` in Chrome and log in.
4. Go to **More → Settings**. Under **Connection** both lines should say **Yes ✓**:
   - **HTTPS** — the page came over an encrypted connection.
   - **One-tap copy** — the browser allows the COPY button to write to the clipboard.

Add it to your home screen from Chrome's `⋮` menu → **Add to Home screen**.

## Why nothing is open to the internet

No router ports are opened and there is no port forwarding: every device makes its own
outgoing, encrypted connection to your tailnet, so there is nothing for the outside world to
connect to. The vault container itself only listens on `127.0.0.1` (this computer), and
Tailscale on the same computer is the only thing that passes requests to it.

## When it doesn't work

| You see | Try |
|---|---|
| Phone: the page never loads | Is the Tailscale app on? Does `tailscale status` on the office computer list the phone? Is the office computer awake (no sleep/suspend)? |
| "This site can't be reached" right after step 4 | Wait a minute for the certificate, then reload. Check `tailscale serve status`. |
| Login says the request didn't come from the vault's pages | `VAULT_ALLOWED_ORIGINS` doesn't match the address in the browser exactly (https, full name, no slash), or the vault wasn't restarted after editing `.env`. |
| You log in and land back on the login page | `VAULT_COOKIE_SECURE=true` but you opened the vault over plain `http://…` from another device. Use the `https://` address. |
| Settings says HTTPS: No | You opened `http://…` or an IP address. Use the `https://…ts.net` address. |
| After a reboot the vault is gone | `systemctl is-enabled tailscaled docker` must say `enabled` twice, and `docker compose ps` should show the vault running. |
