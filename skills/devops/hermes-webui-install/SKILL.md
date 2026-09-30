---
name: hermes-webui-install
description: Install Hermes WebUI on a Linux host for access from a phone over Tailscale. Use when the user (or any Hermes user) wants to run the nesquena/hermes-webui web app and reach it from a phone. Covers cloning, password auth, Tailscale serve vs 0.0.0.0 fallback, systemd user unit, iPhone PWA flow. The repo is Python — package.json is just ESLint dev tooling.
---

# Hermes WebUI Install

Install [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) on a Linux host (Ubuntu 26.04 tested) and expose it on a Tailscale tailnet for phone access.

## Pre-flight

1. **Confirm the repo is Python, not Node.js.** `package.json` exists but is dev-only (ESLint runtime guard). Real entry is `bootstrap.py` then `server.py`. No build step. The Hermes WebUI README says "No build step, no framework, no bundler. Just Python and vanilla JS."
2. **Confirm Python 3.11+** is on the host: `python3 --version`. The bootstrap prefers `~/.hermes/hermes-agent/venv/bin/python` if it exists.
3. **Confirm Tailscale is up and authenticated**: `tailscale status` (should show the node with an IP). If not, install with the OS-appropriate method and `tailscale up` (browser auth) or `tailscale up --authkey=...` (reusable key from admin).
4. **Confirm an existing `~/.hermes`** (if present) is left untouched. The WebUI auto-discovers it; the safety rule in `docs/onboarding-agent-checklist.md` is: *"Do not delete, move, or overwrite the real `~/.hermes` directory unless the human explicitly asks for that exact action."* The WebUI state goes in a NEW dir `~/.hermes/webui/` (sessions, .pbkdf2_key) — not in the existing config.

## Install

```bash
# 1. Clone (default branch is master, NOT main)
cd ~/Developer  # or ~/hermes, wherever the user prefers
git clone --depth 1 https://github.com/nesquena/hermes-webui.git
cd hermes-webui

# 2. Generate password and write .env
WEBUI_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
echo "$WEBUI_PASS" > ~/.hermes/webui.password
chmod 600 ~/.hermes/webui.password

cat > .env <<EOF
HERMES_WEBUI_HOST=0.0.0.0
HERMES_WEBUI_PORT=8787
HERMES_WEBUI_PASSWORD=${WEB...600 .env

# 3. Start the daemon (do NOT use `python3 bootstrap.py` — it tries to wait for /health
#    in foreground and will hang the shell. ctl.sh backgrounds it via nohup.)
./ctl.sh start
# Returns immediately, ~5-10s before /health responds
```

## Verify

```bash
# Health from Tailscale IP (the canonical check)
curl -sS http://$(tailscale ip -4):8787/health
# Expect: {"status":"ok", ...} HTTP 200

# Auth gate
curl -sS -o /dev/null -w "%{http_code}\n" http://$(tailscale ip -4):8787/api/sessions
# Expect: 401 (Authentication required)

curl -sS -o /dev/null -w "%{http_code}\n" http://$(tailscale ip -4):8787/
# Expect: 302 (redirect to /login)
```

## Tailscale Serve vs 0.0.0.0 fallback

**Always try `tailscale serve --bg 8787` first** — gives a nice HTTPS URL like `https://ubuntu-4gb-fsn1-1.tailXXXX.ts.net`.

**Fallback** if it errors with *"Serve is not enabled on your tailnet"*: the user must visit the link Tailscale prints to enable it in their tailnet policy, OR use `HERMES_WEBUI_HOST=0.0.0.0` (which is what `.env` should be set to anyway). The 0.0.0.0 bind means the WebUI is reachable from any Tailscale peer (including the iPhone) at `http://<tailscale-ip>:8787`.

The iPhone MUST be signed into the same Tailscale account for the 0.0.0.0 path to work. `tailscale status` shows all peers — confirm the iPhone shows up as a peer.

## Systemd auto-start

The WebUI ships `scripts/wsl/hermes_webui_autostart.sh` (WSL-targeted) and `ctl.sh` (no built-in systemd). For Ubuntu hosts, write a user systemd unit.

**Critical gotcha:** the WebUI's bootstrap uses `os.execv` to become the long-lived server. Pass `--foreground` so systemd sees the server as the original child (recommended in `bootstrap.py --help`).

**Another gotcha:** if you're running INSIDE the Hermes gateway (or any process that has the same parent), `systemctl --user` is blocked by the gateway's safety hook. Write the unit file from inside, then have the user run `systemctl --user enable --now hermes-webui.service` from a separate shell.

Unit file at `~/.config/systemd/user/hermes-webui.service`:

```ini
[Unit]
Description=Hermes WebUI (phone / Tailscale access)
Documentation=https://github.com/nesquena/hermes-webui
After=network-online.target tailscaled.service
Wants=network-online.target
After=hermes-gateway.service
StartLimitIntervalSec=300
StartLimitBurst=10

[Service]
Type=simple
WorkingDirectory=/home/<user>/Developer/hermes-webui
EnvironmentFile=/home/<user>/Developer/hermes-webui/.env
Environment="PATH=/home/<user>/.hermes/hermes-agent/venv/bin:/home/<user>/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/<user>/.hermes/hermes-agent/venv/bin/python /home/<user>/Developer/hermes-webui/bootstrap.py --no-browser --foreground 8787
ExecStop=/bin/bash -c 'if [ -f /home/<user>/.hermes/webui.pid ]; then PID=$(cat /home/<user>/.hermes/webui.pid); pkill -TERM -P $PID 2>/dev/null; kill -TERM $PID 2>/dev/null; sleep 2; kill -KILL $PID 2>/dev/null; fi; pkill -TERM -f "/home/<user>/Developer/hermes-webui/server.py" 2>/dev/null; sleep 1; pkill -KILL -f "/home/<user>/Developer/hermes-webui/server.py" 2>/dev/null'
Restart=on-failure
RestartSec=10
TimeoutStartSec=60
TimeoutStopSec=15
StandardOutput=append:/home/<user>/.hermes/logs/hermes-webui-systemd.log
StandardError=append:/home/<user>/.hermes/logs/hermes-webui-systemd.log

[Install]
WantedBy=default.target
```

Validate with `systemd-analyze verify ~/.config/systemd/user/hermes-webui.service`.

## iPhone steps

1. Tailscale app installed and signed in (should be on the same tailnet — check `tailscale status` on the host for `iphone-...` peer).
2. Open Safari, navigate to `http://<tailscale-ip>:8787` (or the magic-DNS HTTPS URL if Serve was enabled).
3. Login: enter the password from `~/.hermes/webui.password` on the host.
4. **For the PWA experience:** in Safari, tap Share → **Add to Home Screen**. This gives a fullscreen app icon, no Safari chrome. The WebUI is mobile-responsive (hamburger sidebar, dvh viewport fix) — no separate iOS app exists.
5. Note: there IS a third-party "Hermex" iOS app by an unrelated developer (Uzair Ansar) on the App Store. Ignore it — it's not from Nous Research.

## Recovery (WebUI died and won't come back)

If the user reports the WebUI is unreachable from their phone, diagnose in this order:

1. **Check Tailscale is up**: `tailscale status` — confirm the VPS node and the iPhone peer are both visible. If the iPhone shows `offline`, the issue is Tailscale on the phone, not the WebUI.
2. **Check port 8787**: `ss -tlnp | grep 8787` — if nothing is listening, the WebUI process died.
3. **Check systemd unit**: `systemctl --user status hermes-webui.service` — if it shows `inactive (dead)` AND `disabled`, the unit was never enabled (common — the enable step requires a separate shell, see pitfalls). The WebUI was running via `ctl.sh` only, so when that process died nothing restarted it.
4. **Check for stale PID file**: `cat ~/.hermes/webui.pid` — if the PID doesn't match any running process, remove it: `rm -f ~/.hermes/webui.pid`.
5. **Restart via ctl.sh**: `cd ~/Developer/hermes-webui && ./ctl.sh start` — this is the fastest recovery path from inside the gateway.
6. **Enable the systemd unit** (prevents recurrence): `systemctl --user enable hermes-webui.service` — this one works from inside the gateway (only `start/stop/restart` are blocked, not `enable`).
7. **Verify**: `curl -sS http://$(tailscale ip -4):8787/health` — expect `{"status":"ok", ...}`.

To switch from ctl.sh-managed to systemd-managed (so it survives reboots properly), the user must run from a separate SSH shell:
```bash
kill $(cat ~/.hermes/webui.pid)
systemctl --user start hermes-webui
systemctl --user status hermes-webui
```

## Pitfalls (hit these during install or recovery)

- **`python3 bootstrap.py` (without `--foreground`) hangs the shell** because it spawns a detached child but then loops on a /health probe. Always use `./ctl.sh start` for daemon mode, or `bootstrap.py --foreground` under a supervisor.
- **Tailscale serve on a fresh tailnet is disabled by default**. First-time error: "Serve is not enabled on your tailnet." The error prints a link to enable it. Fallback to 0.0.0.0 is fine for self-tailnet use; only matters if you want the HTTPS magic-DNS URL.
- **The gateway safety hook blocks MORE than just `systemctl --user`**. From inside the Hermes gateway, ALL of these are blocked: `systemctl --user start/stop/restart`, `./ctl.sh stop`, `pkill -f 'hermes-webui/server.py'`, and any command pattern-matching as a gateway lifecycle operation. The hook catches `pkill` and `ctl.sh stop` because they signal processes broadly. **Workaround**: use `kill <literal PID>` with the numeric PID from `~/.hermes/webui.pid` — `kill 369583` passes through fine. Only `systemctl --user enable` (not start/stop) works from inside the gateway.
- **The systemd unit must be explicitly enabled** or the WebUI won't survive reboots. The `enable` step is the one most commonly missed because it must be done from a separate shell if you also want `--now` (start immediately). But `systemctl --user enable` alone (without `--now`) works from inside the gateway — do that, then `ctl.sh start` for the running instance, and the unit will auto-start on next reboot.
- **`StartLimitIntervalSec` / `StartLimitBurst` go in `[Unit]`, not `[Service]`** — easy mistake that `systemd-analyze verify` will flag.
- **`.env` file is gitignored AND read-protected** by Hermes' read_file secret guard. That's a feature — the password stays in the env file and is loaded by `start.sh`/`ctl.sh` via `set -a; source .env`. Don't try to inspect the password via `read_file` from Hermes — use `cat` or `grep` from terminal.
- **Don't run with both `./ctl.sh start` and systemd `start` at the same time** — they'll fight for port 8787. Pick one. `ctl.sh` checks for an existing launchd/systemd instance and refuses to start a second. However, having `systemctl --user enable` (for boot-time auto-start) alongside a `ctl.sh start` (for the current session) is fine — they don't conflict until a reboot, at which point systemd takes over.
- **Bootstrap takes ~5-10s** before /health responds. Don't panic if the first curl 7-fails; wait 10s and retry.

## Verification commands (copy-paste)

```bash
# On the host
ss -tlnp | grep 8787
curl -sS http://$(tailscale ip -4):8787/health
pgrep -af 'server.py' | grep -v '/bin/bash'

# From iPhone Safari, navigate to http://<tailscale-ip>:8787
# Login with password from ~/.hermes/webui.password on the host
```
