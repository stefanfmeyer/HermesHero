# OS Choice for the Hermes Destination Host

The user's July 2026 migration targeted an HP ProDesk 400 G5 (8GB RAM, 256GB SSD, 1TB HDD). RAM is the binding constraint. Here is the honest comparison for headless Linux on a mini-PC running Hermes 24/7.

## Recommendation: Debian 13 (Trixie)

**Why Debian 13 Trixie over Debian 12 (Bookworm):**

- Trixie released August 2025, Bookworm superseded. The official Debian site shows the Bookworm install page as deprecated.
- Trixie ships **Python 3.13** in repos (Bookworm: 3.11). Hermes requires 3.11+, and 3.13 works fine. Forward-compatible for future Hermes releases.
- Trixie support until **August 2028** (LTS to June 2030). 5-year lifecycle vs Bookworm's remaining 2-3 years.
- Same installer, same `apt`, same Tailscale repo URL pattern.

## Distro Comparison

| Distro | Idle RAM | Stability | Hermes fit | Verdict |
|---|---|---|---|---|
| **Debian 13 Trixie** | ~250-300MB | Rock solid | Python 3.13 in repos, Docker first-class | ✅ Best |
| Debian 12 Bookworm | ~250-300MB | Rock solid | Python 3.11 | Fine but superseded |
| Ubuntu Server 24.04 | ~400-500MB | Good | Same as Debian + snapd bloat | Fine but heavier |
| Ubuntu Server 26.04 | ~450MB | Newer, less battle-tested | Newer kernels | OK but unnecessary |
| Alpine | ~80MB | Good | musl libc breaks Python venvs | ❌ Compatibility risk |
| Arch | ~300MB | Rolling = risky unattended | Bleeding edge | ❌ Not for 24/7 |
| Proxmox VE | ~1GB base | Good | Hypervisor tax on 8GB | ❌ Too heavy (user already decided) |

## Trixie Download (Verified 2026-07-23)

The Debian website's `/releases/trixie/install` link is broken (returns 404). The correct direct download:

```
https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso
```

This redirects via 302 to a regional mirror. The file is ~600MB, netinst (pulls the rest from the network during install).

For the user's specific setup (Bazzite Mac mini downloading, then flashing to USB for the ProDesk), the recommendation was:
1. **Bazzite already has Ventoy installed** (per user profile) → just copy the ISO to the Ventoy USB stick
2. Or use `dd` / balenaEtcher if Ventoy is not available

## Installer Notes (Debian 13)

Headless install — check ONLY these two in the tasksel screen:
- ✅ SSH server
- ✅ Standard system utilities

Leave unchecked: Desktop environment, print server, web server, file server.

Partitioning: **Guided — use entire disk** for the 256GB SSD. The 1TB HDD gets formatted and mounted manually after first boot (the installer only sees the boot disk by default — that's fine, the HDD will be detected after).

GRUB: install to the SSD (default first disk).

## Post-install Essentials

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git wget vim ufw fail2ban sqlite3
```

The `sqlite3` package is needed for the `state.db VACUUM` step in `templates/hermes-storage-sweep.sh`. If the user objects, the script will skip the vacuum step silently (it checks `command -v sqlite3` first).

## Tailscale Install for Trixie (Verified 2026-07-23)

```bash
# Add Tailscale's official repo (Trixie-specific)
curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt update
sudo apt install -y tailscale
sudo tailscale up --ssh
```

The `trixie` codename in the repo URL is correct — Tailscale's repo is codename-keyed, not generic. If this errors with "no installation candidate", the codename may not be published yet for that specific Trixie minor version; fall back to `bookworm` (the repo is API-compatible and Tailscale supports cross-codename install).

## If the User Argues for Ubuntu

Common reasons: "more familiar", "easier to find tutorials for", "Snap store".

Counter-arguments:
- Snap store is irrelevant on a headless server (no GUI to install snaps)
- Ubuntu is built FROM Debian. Anything that works on Debian works on Ubuntu
- Ubuntu Server ships snapd by default → consumes ~50-100MB idle RAM + a daemon
- Ubuntu's `apt` is the same `apt` as Debian's. Tutorials work identically.
- Ubuntu's release cycle is faster → more frequent forced upgrades

If the user still wants Ubuntu, the recipe is the same — just replace `trixie` with `noble` in the Tailscale repo URL and use Ubuntu's netinst ISO.

## What Was Used (July 2026)

The user landed on Debian 13 Trixie netinst after I asked "is debian 12 headless the best linux to use for this setup?" and showed the comparison table. The actual install steps were:
1. Flashed ISO to USB via Ventoy on Bazzite
2. Booted ProDesk from USB, headless install
3. Installed Tailscale, got `tailscale ip -4` output
4. Gave agent the Tailscale IP → agent SSHed in to do the rest
