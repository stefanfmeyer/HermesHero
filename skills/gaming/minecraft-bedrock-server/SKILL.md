---
name: minecraft-bedrock-server
description: "Host a Minecraft Bedrock Dedicated Server (BDS) on Linux — download, config, firewall, backups, in-place upgrades, console (PS5/Xbox/Switch) connections via BedrockConnect."
tags: [minecraft, bedrock, gaming, server, bds]
related_skills: [minecraft-modpack-server]
---

# Minecraft Bedrock Dedicated Server (BDS)

## When to use
- User wants a Bedrock Edition server (BDS) for Bedrock clients (Windows/mobile/console)
- Questions about Bedrock server resources, shaders, or client connectivity
- Note: Java/Forge/NeoForge modded servers are a different beast — see minecraft-modpack-server

## Key facts
- BDS is a **native binary, not a JVM** — very light: 1-2GB RAM, single-threaded-leaning. An old 4-core i3 with 17GB free comfortably handles 5-10 players. Compare: modded Java packs want 6-24GB.
- **Shaders are CLIENT-SIDE ONLY.** The server cannot force or run shaders. Closest server-side option: `texturepack-required=true` (textures, not lighting). Don't promise server-side shaders.
- Default gameplay port **19132/UDP** (IPv4) + 19133/UDP (IPv6). Both gameplay AND LAN discovery.

## Steps
### 1. Get the download URL
The official page (minecraft.net/en-us/download/server/bedrock) renders the link via JS — grep on the HTML will NOT find the .zip. Probing the direct URL pattern works:
```
https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-<VERSION>.zip
```
Find current version from recent Mojira bugs (mojira.dev) mentioning `bedrock-server-X.Y.Z.W.zip`, or try likely versions. See `references/setup-2026-09.md` for a real transcript. Seed extraction, sleeper-percentage, and post-upgrade session addenda: `references/seed-and-sleep-2026-09.md`.

### 2. Download (use wget, not curl)
curl consistently fails against minecraft.net with `HTTP/2 stream not closed cleanly` / `unexpected EOF` (HTTP/1.1 also fails on this CDN). **wget works first try:**
```bash
mkdir -p ~/minecraft-bedrock && cd ~/minecraft-bedrock
wget -q --tries=2 --timeout=45 "https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-<VER>.zip" -O bedrock-server.zip
unzip -oq bedrock-server.zip -d server
```

### 3. Configure server.properties
Defaults are survival/easy/10 players. For a small survival server change only what's needed:
```properties
difficulty=normal        # default is easy
gamemode=survival
online-mode=true
allow-list=false
server-port=19132
playerssleepingpercentage=1   # only 1 player must sleep to skip night (Bedrock key; default 100 requires everyone)
```
Changes to server.properties require a server restart to apply — wait until all players have disconnected before bouncing it. Note `playerssleepingpercentage` is NOT present in the default properties file; append it.
Then accept EULA: `echo "eula=true" > server/eula.txt` (required, server exits without it).

### 4. Firewall + launch
```bash
sudo ufw allow 19132/udp comment "Minecraft Bedrock"
cd ~/minecraft-bedrock/server && LD_LIBRARY_PATH=. ./bedrock_server
```
Run via Hermes `terminal(background=true, notify_on_complete=true)` so lifecycle is tracked and logs are readable via `process(action='log')`. Server is ready when log shows `Server started.` (~5-15s, no worldgen delay like Java).

### 5. IPs to give the user
`hostname -I` gives both LAN and Tailscale IPs. Report LAN IP for same-network players and Tailscale IP for remote. Bedrock LAN discovery finds it automatically on same network.

### 6. Backups
BDS world lives in `server/worlds/` (NOT `world/` like Java).

**Use the managed script, not a raw crontab line:** `~/.hermes/scripts/bedrock-backup.sh`
(scheduled 04:00 daily via `crontab -l`; freshness watchdog = Hermes cron job
`bedrock-backup-check.sh`, silent unless the newest backup is >36h old).
It archives `worlds/` + the **live** install's config files, integrity-checks the
tar before promoting it, prunes >30d, and mirrors to
`/mnt/storage/hermes/minecraft-backups/`.

**CRITICAL PITFALL — `%` in crontab commands.** This was the actual failure of the
original naive line:
```
0 4 * * * tar -czf ~/minecraft-bedrock/backups/world_$(date +%Y-%m-%d).tar.gz -C ~/minecraft-bedrock/server worlds
```
In a crontab, an **unescaped `%` terminates the command**; the rest becomes stdin.
`date +%Y-%m-%d` was silently truncated to `date +`, `tar` never ran, and because
the `2>>backup.log` redirect sat *after* the `%` it was never set up either — so
there was no error anywhere. The cron journal still logged `CMD (...)` every night,
making it look healthy. **Fix: never put `%` in a crontab line — call a script.**
If you must inline it, escape as `\%`.

Diagnosing "the backup cron isn't working" here:
1. `ls ~/minecraft-bedrock/backups/` — empty despite daily `CMD` journal entries ⇒ this bug.
2. `crontab -l | cat -A` — look for `%` in the command portion.
3. `sudo journalctl -u cron --since "4 days ago" | grep -i bedrock` — shows the
   truncated command as cron actually parsed it.
4. Absence of the expected `backup.log` is the tell: the redirect was discarded too.

**PITFALL — two server installs.** Upgrades land side-by-side (`server/` = old,
`server-1.26.45.1/` = live) and the new install symlinks `worlds` back to
`server/worlds`. So the world is always at `server/worlds`, but the **live
`server.properties` is in the newest install dir**. A naive backup of `server/`
captures a stale config (or a `.bak-` file). Pick the config dir by newest mtime
that actually contains a `server.properties`.

Live-backup safety: tarring a running BDS is a point-in-time read of a LevelDB;
the newest `.log` segment can be caught mid-append, but LevelDB recovers from a
torn tail record, so it's safe in practice. Always `gzip -t` + `tar -tzf` verify
before promoting the archive.

### 7. Upgrading BDS in place (version mismatch)
Client error "the host is using an older version of Minecraft" = BDS build lags the client. Clients auto-update; servers never do. Don't guess versions off the webpage — re-probe the URL pattern from step 1 for the newest 4-part version (e.g. `1.26.45.1`; only 4-part versions exist, `1.26.45` is not a real filename). Upgrade procedure preserving the world:
1. Download + unzip the new version to `server-<newver>/` alongside the old install
2. Copy `server.properties` and `eula.txt` from the old server dir
3. Symlink the world: `ln -sfn ~/minecraft-bedrock/server/worlds server-<newver>/worlds`
4. Stop the old process, start the new one on the same port. Clients just reconnect — same IP/port, world intact.

**BREAKING NETWORKING CHANGE — `transport=nethernet` (introduced ~1.26.51.1).**
Recent BDS releases ship **NetherNet** as the *only* supported transport. If an upgrade
crosses this boundary the server still starts and still prints `Server started.`, but logs a
prominent error block and **no players can connect**:

```
ERROR ================ TRANSPORT TYPE ERROR  ===================
ERROR Your current connection type is not set to NetherNet. In this release,
      NetherNet is the only supported transport type.
ERROR Players will not be able to connect to your game without NetherNet.
ERROR To switch, set 'transport=nethernet' in server.properties.
```
This is a `server.properties` key that **does not exist in the default/older file** — you
must append it, and it needs a restart to take effect.

NetherNet also **inverts the networking model** vs RakNet:
| | RakNet (pre-nethernet) | NetherNet |
|---|---|---|
| `server-port` (19132) | UDP gameplay | **TCP** HTTP signalling/handshake |
| `server-portv6` (19133) | UDP gameplay (IPv6) | (not used as a separate gameplay port) |
| gameplay | same UDP socket | **negotiated UDP**, ports from the OS ephemeral range |
| firewall need | `19132/udp` | **`19132/tcp`** + a UDP gameplay range |

Because gameplay UDP is drawn from the ephemeral range by default (`32768-60999` here), you
**cannot firewall it** unless you pin it. Set a fixed range, then open exactly that:
```properties
transport=nethernet
server-udp-ports=32000-32100        # pin local UDP allocation to a firewall-openable range
```
```bash
sudo ufw allow 19132/tcp comment "Minecraft Bedrock NetherNet signalling"
sudo ufw allow 32000:32100/udp comment "Minecraft Bedrock NetherNet gameplay"
```
Keep the old `19132/udp` rule — harmless, and needed if you ever fall back to `transport=raknet`.

Verify the switch took (before/after a restart):
```bash
ss -ltnp | grep 19132      # MUST show a tcp LISTEN — absent = still on raknet
curl -s -m 5 -o /dev/null -w '%{http_code}\n' http://<LAN-IP>:19132/   # 404 = signalling alive
```
`HTTP 404` on `/` is **correct** — the port speaks HTTP but has no route at `/`; it is the
handshake endpoint. TCP-connect success is the signal, not the status code.

`server-udp-ports` syntax (all optional): `internal | start-end`,
`[ip:]external[-external]:internal[-internal]`, comma-separated, repeatable across lines.
Use the mapping form only behind NAT/port-forwarding; on a plain LAN just use a bare range.

Console (PS5/Xbox/Switch) note: BedrockConnect's DNS trick targets the *RakNet* UDP flow.
Under NetherNet the console still needs `19132/tcp` reachable plus the advertised UDP range —
if console joins fail after this upgrade, that mismatch is the first thing to check.

**`transport=raknet` IS NOT A WORKING FALLBACK on 1.26.51.1 — do not trust the docs.**
The how-to still lists `raknet` as an allowed value and playit.gg's own support page tells you
to set it as a bandaid. **Tested and disproved here:** with `transport=raknet` the server logs
`Server started.` but binds **no** listener on 19132 (the `transport=raknet` run showed only
udp/19133 + ephemeral), `/v1/join` returns *empty*, and the
`TRANSPORT TYPE ERROR` block appears **in that very run's log**. Confirm by run, not by config:
check `ss -ltnp | grep 19132` for the TCP listener — if it is absent, that transport is dead in
this build. Revert to `nethernet`.

**External access needs TWO things — this is WebRTC, not a simple port forward.**
NetherNet is WebRTC-based (`df-mc/nethernet-spec`): LAN discovery broadcasts on fixed **UDP
7551**; peers negotiate ICE candidates and then run DTLS/SCTP directly. The docs' line "only
signalling needs the proxy — gameplay flows directly between client and server" means the UDP
gameplay path **bypasses your TCP tunnel** and still needs its own route to the host.

**Check for double NAT before promising external access.** Walk the route:
```bash
ip -4 route | grep default        # our gateway
traceroute -n -m 5 1.1.1.1        # a PRIVATE (10./172./192.) hop past our router = double NAT
```
If a private hop sits between the GL.iNet and the ISP, port forwarding needs configuring on
**both** routers and the upstream one usually is not yours. Test the real public IP directly
(not from inside the LAN — hairpin NAT makes that lie):
```bash
curl -s -m 8 -o /dev/null -w '%{http_code}\n' http://<PUBLIC_IP>:19132/v1/join
```

**`/v1/join` is the one-call health check** — it returns JSON over TCP 19132 with no client:
```bash
curl -s http://<host>:19132/v1/join
# {"name":"Dedicated Server","protocol":2193,"version":"1.26.51","level":"...","players":0,...}
```
Empty output, or no TCP 19132 listener, means the transport is not actually up even if the log
says `Server started.`.

**Tunnel providers when direct exposure is impossible.** playit.gg requires **Premium ($3/mo)**
for a TCP+UDP tunnel — the free tier is UDP-only, which is useless for NetherNet since the
signalling is TCP. Setup (per a working playit forum report) needs **two tunnels**:
- TCP, 1 port, → `127.0.0.1:19132` (this is the hostname players enter)
- UDP, 4 ports, → the server's **LAN** address on playit's assigned range

and `server-udp-ports` must use **identical external and internal ports**
(`ip:61226-61229:61226-61229`); mismatched pairs make the server bind nothing while still
printing `Server started.` Players never enter the UDP address — the server advertises it.

**UPnP/NAT-PMP:** check before giving up on automatic forwarding —
`upnpc -l` (install `miniupnpc`). "No IGD UPnP Device found" is common on GL.iNet and means
you cannot request forwards programmatically, so admin creds are needed.

**Reachability testing pitfall — bash `/dev/tcp` gives FALSE POSITIVES on filtered ports.**
A `timeout N bash -c 'cat </dev/null >/dev/tcp/HOST/PORT'` reported an ISP-filtered port as
OPEN here. Use `curl -s -m N -o /dev/null -w '%{http_code}'` — a filtered/unreachable port
correctly yields `000`. Prefer curl (or `nc -z` with an explicit timeout) for the final verdict.
`InitialConnection-45`/`-34` *after* TCP signalling succeeds and tcpdump proves bidirectional UDP
reachability, i.e. a NetherNet negotiation failure, not a firewall/NAT problem. LAN works.
So an external-access failure in this build may be unfixable from the server side; do not spend
hours on firewall rules before checking the current state of that report.

### 8. Console connections (PS4/PS5/Xbox/Switch) — BedrockConnect
Consoles have NO "Add Server" button; custom IPs are directly unreachable. Use the BedrockConnect DNS trick (github.com/Pugmatt/BedrockConnect):

On the console: Network settings → Set Up Internet Connection → Advanced Settings → DNS Settings → Manual. Primary DNS `104.238.130.180`, Secondary `8.8.8.8`. Then in Minecraft: Play → **Servers** tab → join any featured server → BedrockConnect menu appears → Connect to Server → enter the server's **LAN IP** + port 19132.

- Consoles are not on Tailscale — always give the LAN IP
- PS5 bug MCPE-239057: LAN servers often never appear in the Friends/LAN tab; the DNS method is the reliable path
- First connect prompts Microsoft account sign-in (matches `online-mode=true`)
- Fallback if public DNS is down: self-host a BedrockConnect instance on the server

### 9. Standing run orders — running indefinitely, and stopping on request
When the user says keep it running until they say stop: never schedule a stop
timer, explicitly exclude `bedrock_server` from any idle/dev-server reaper
scripts (even if it's technically out of scope for them), and record the
standing order so future sessions honor it.

**START IT VIA THE SCRIPT, NOT A HERMES BACKGROUND PROCESS.**
`~/.hermes/scripts/bedrock-server.sh {start|stop|restart|status}`

Launching with `terminal(background=true)` puts the server inside the
**`hermes-gateway.service` cgroup**, parented to the gateway process. It then
dies on the next gateway restart — this is precisely how the server was lost on
the 2026-09-10 reboot, and it looks healthy in the interim.

**`setsid` is NOT sufficient to fix this.** `setsid` gives the process a new
session but leaves it in the same cgroup. When the launcher is Hermes, that
cgroup belongs to the gateway, so the server still dies with it. Use a
transient systemd scope, which the gateway does not own:

```bash
systemd-run --user --scope --quiet --collect --unit="bedrock-server-$(date +%s)" \
  env LD_LIBRARY_PATH=. ./bedrock_server >>"$LOG" 2>&1 </dev/null &
```

Verify detachment with BOTH checks — session alone is misleading:
```bash
p=$(pgrep -x bedrock_server | head -1)
cat /proc/$p/cgroup                 # must NOT contain hermes-gateway
ps -o ppid= -p $p                   # must be systemd --user (usually 830)
```
A correct result shows its own `.../app.slice/bedrock-server-<epoch>.scope`.

Note: a scope still does **not** survive a reboot (intentional — the user did
not want it auto-starting as a service). After a reboot, run
`bedrock-server.sh start`. `--collect` prevents stale scopes from accumulating;
the `--unit` is timestamped so restarts don't collide with the old unit name.

### 10. Extracting the world seed (for Chunkbase etc.)
Read it from the `level.dat` file in the world directory — NOT from the LevelDB:
```python
import struct
body = open('<worlddir>/level.dat','rb').read()[8:]   # skip 4-byte version + 4-byte length header
i = body.find(b'RandomSeed')
seed = struct.unpack('<q', body[i+10:i+18])[0]        # int64 LE right after the name
```
- Structure check: the 3 bytes before `RandomSeed` are `[tag=0x04][name_len u16 LE = 0a 00]`; the 8 bytes after the name are the int64 seed.
- Chunkbase accepts the signed int64 as-is; unsigned form is the same value mod 2^64.
- Do NOT hunt for the seed inside `worlds/<name>/db/` (the LevelDB): BDS stores world data with nonstandard compression (raw DEFLATE = trailer type 4, not snappy/zlib), LevelDat is NOT a key in the db, and .ldb/.log parsing burns 15+ tool calls for nothing. `level.dat` is right there in the world dir — 5-second answer. The `Overworld`-prefixed db key is dimension metadata, not the seed.

### 11. Stopping on request (standing order fulfilled)
When the user says stop — e.g. a bare "stop bedrock_server" — the indefinite-run
standing order from step 9 is now SATISFIED: stop cleanly, then **update the
standing order note**, or a future session will re-read "never stop it" and
refuse or silently restart it.

```bash
~/.hermes/scripts/bedrock-server.sh stop     # SIGTERM, waits 30s, escalates to SIGKILL
```

**Before stopping, verify nothing will restart it** — do this in the same pass,
not after:
```bash
crontab -l | grep -i -E "bedrock|minecraft"   # should be the backup line only
systemctl --user list-units --all | grep -i bedrock
# then check the Hermes cron list for any job whose script/prompt restarts it
```
In this environment the Minecraft Hermes crons are **backup-only** (the
`bedrock-backup-check.sh` watchdog reports freshness, it does not restart), and
`kill-stale-dev-servers.sh` already excludes `bedrock_server` — so a stop is
final. Don't assume that shape in a new environment; check.

**PITFALL — a graceful BDS shutdown logs NOTHING.** `SIGTERM` does not produce
`Server stopped.` / `Stopping server...` / `Saving worlds...` lines. The log
simply ends at the last `Server started.` (or telemetry banner) entry. So
**"no shutdown in the log" is NOT evidence of an unclean exit** — do not
diagnose a failed shutdown from log silence. Confirm by process/port instead:

```bash
pgrep -x bedrock_server || echo "gone"          # process reaped
ss -lunp | grep 19132 || echo "port released"   # UDP socket freed
ls ~/minecraft-bedrock/server/worlds/*/db/LOCK   # no LOCK left behind
```
A `db/00XXXX.log` whose mtime is ~seconds after `Server started.` means LevelDB
closed out that segment normally.

**Take a fresh verified backup after the stop.** The server being down makes this
a clean point-in-time snapshot of the FINAL world state — strictly better than
the routine 4am live-tar.
```bash
~/.hermes/scripts/bedrock-backup.sh
gzip -t ~/minecraft-bedrock/backups/world_<date>.tar.gz && echo OK
tar -tzf ~/minecraft-bedrock/backups/world_<date>.tar.gz | head   # expect worlds/<name>/db/...
ls -la /mnt/storage/hermes/minecraft-backups/                     # mirror landed
```

**`%` and shell quoting:** when retaining a shutdown summary to Hindsight, a
`-d '...'` curl payload containing parentheses (`(~/minecraft-bedrock...)`, `(1)...`,
`(2)...`) breaks bash — `syntax error near unexpected token '('`. Write the JSON to
a file and use `-d @/tmp/payload.json`. Also avoid `%` in crontab lines (step 6).

Report the stop as: process gone, port released, nothing will restart it, backup
verified, and **the one command to bring it back**
(`~/.hermes/scripts/bedrock-server.sh start` — it does not survive a reboot).

## Verification
- `ss -ulnp | grep 19132` shows the bedrock_server process listening
- `pgrep -fa bedrock_server` process alive
- Log line `Server started.` = ready; player joins log as `Player connected`
- Detachment check (see step 9): `/proc/<pid>/cgroup` must NOT mention
  `hermes-gateway`, and ppid must be `systemd --user`
- After a stop: `pgrep -x bedrock_server` empty AND `ss -lunp | grep 19132` empty
  (both, not just one)

## Pitfalls
- curl (even with --http1.1, retries, resume) fails on minecraft.net CDN; use wget
- Must run from server dir with `LD_LIBRARY_PATH=.` or the binary can't find its bundled libs
- No eula.txt → silent immediate exit
- `release-notes.txt` in the zip states the BDS version — sanity-check it matches what you downloaded
- Backup path is `worlds/` plural; Java skill's backup scripts reference `world/` and won't work as-is
- Version probing: `wget --spider` on the URL pattern works; `curl -s -o /dev/null -w %{http_code}` returns 000 against minecraft.net even when the file exists — don't treat 000 as "not found", verify with wget
- **Third-party "latest version" trackers go stale** — the official page is JS-rendered and
  grep/search snippets lag. DoomHosting's list claimed 1.26.33 while 1.26.45.1 was already
  installed and 1.26.51.1 was live. Never upgrade *downward* off a tracker: compare the
  tracker against the release-notes version of the running install, then bracketed-probe the
  URL pattern upward (`for v in X.Y.Z.1; do wget --spider ...; done`) to find the real newest.
  Confirm the probe isn't a false positive by checking the response is a real zip (size ~90M),
  not an error page.
- Version mismatch after a client auto-update is routine — the upgrade-in-place procedure (step 7) takes ~2 minutes, world survives via symlink
- **Upgrades crossing into NetherNet (≈1.26.51.1+) need `transport=nethernet` appended to
  server.properties or NOBODY can connect** — the server starts fine and logs `Server started.`,
  so a port check alone will not catch it. See step 7. Firewall must become `19132/tcp` +
  a pinned `server-udp-ports` UDP range; gameplay no longer rides on 19132/udp
- A `server.properties` edit silently does nothing until the server is **restarted** — verify by
  socket, not by reading the file back (`ss -ltnp | grep 19132` for the TCP switch)
- **`bedrock-server.sh restart` can race** — the replacement process sometimes fails to bind
  TCP 19132 while still logging `Server started.`, leaving no listener. Prefer a clean
  `stop` → confirm `pgrep -x bedrock_server` empty and ports free → `start`. Always verify with
  `ss -ltnp | grep 19132` and a `/v1/join` curl, never with the log line
- **`transport=raknet` does not work on 1.26.51.1** even though the docs and playit.gg's support
  page say it does (tested — no listener, empty `/v1/join`, error in-run). See step 7
- NetherNet is **WebRTC**, so a TCP tunnel alone cannot publish a server: gameplay UDP bypasses
  the tunnel. Check for double NAT (`traceroute`) and for global IPv6 before promising external
  access; ULA-only addressing (`fdda:`/`fd7a:`) is not a workaround
- Mojang bug **BDS-23110**: external joins can fail after connectivity is proven — that is a
  server-side protocol defect, not your firewall
- **Never launch via `terminal(background=true)`** — lands in the gateway cgroup and dies with it (step 9)
- **`setsid` does not escape a cgroup** — use `systemd-run --user --scope` (step 9)
- Two install dirs coexist after an upgrade; the live `server.properties` is in the
  NEWEST one, the world is always at `server/worlds` (step 6)
- Never place `%` in a crontab command line — it truncates the command silently (step 6)
- Verify a cron actually RAN, not just that it was scheduled: `last_status: "ok"` and
  journal `CMD (...)` lines both appear even when the command dies instantly. Look for
  the artifact (backup file) and the script's own log.
- **BDS logs nothing on SIGTERM** — absence of a shutdown line in `server.log` is
  normal, not a failed stop. Verify with process + port, never with the log (step 11)
- A fulfilled standing order must be **written back**: if you stopped the server on
  request but left the note saying "never stop it", the next session will fight you
  (step 11)
- Retaining a shutdown summary to Hindsight with `curl -d '...'` breaks on
  parentheses — use `-d @file.json` (step 11)

## Reference
- `references/setup-2026-09.md` — original install transcript
- `references/seed-and-sleep-2026-09.md` — seed extraction, sleeper-percentage
- `references/shutdown-2026-09.md` — verified stop + final-backup transcript, and the
  restart-to-stop-to-restart standing-order lifecycle