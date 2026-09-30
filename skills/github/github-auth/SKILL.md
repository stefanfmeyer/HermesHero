---
name: github-auth
description: "GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, Authentication, Git, gh-cli, SSH, Setup]
    related_skills: [github-pr-workflow, github-code-review, github-issues, github-repo-management]
---

# GitHub Authentication Setup

This skill sets up authentication so the agent can work with GitHub repositories, PRs, issues, and CI. It covers two paths:

- **`git` (always available)** — uses HTTPS personal access tokens or SSH keys
- **`gh` CLI (if installed)** — richer GitHub API access with a simpler auth flow

## Detection Flow

When a user asks you to work with GitHub, run this check first:

```bash
# Check what's available
git --version
gh --version 2>/dev/null || echo "gh not installed"

# Check if already authenticated
gh auth status 2>/dev/null || echo "gh not authenticated"
git config --global credential.helper 2>/dev/null || echo "no git credential helper"
```

**Decision tree:**
1. If `gh auth status` shows authenticated → you're good, use `gh` for everything
2. If `gh` is installed but not authenticated → use "gh auth" method below
3. If `gh` is not installed → use "git-only" method below (no sudo needed)

---

## Method 1: Git-Only Authentication (No gh, No sudo)

This works on any machine with `git` installed. No root access needed.

### Option A: HTTPS with Personal Access Token (Recommended)

This is the most portable method — works everywhere, no SSH config needed.

**Step 1: Create a personal access token**

Tell the user to go to: **https://github.com/settings/tokens**

> ⚠️ **Classic vs Fine-grained PATs — CRITICAL distinction:**
> - **Classic PAT** (`ghp_` prefix): select `repo` scope → works for all repos, all operations. **Use this for agent/backups.**
> - **Fine-grained PAT** (`github_pat_` prefix): must grant per-repo permissions including **"Contents: Read and write"** for push. The API may show `push: true` (user's permission) while `git push` returns 403 ("Write access not granted") because the token itself lacks the Contents permission. **Avoid for automated workflows unless you explicitly configure per-repo permissions.**
> - To verify a token has write access: `curl -X PUT -H "Authorization: token <token>" https://api.github.com/repos/<owner>/<repo>/contents/test -d '{"message":"test","content":"dGVzdA=="}'` — if it returns "Resource not accessible by personal access token", the token needs more permissions.

- Click "Generate new token (classic)"
- Give it a name like "hermes-agent"
- Select scopes:
  - `repo` (full repository access — read, write, push, PRs)
  - `workflow` (trigger and manage GitHub Actions)
  - `read:org` (if working with organization repos)
- Set expiration (90 days is a good default)
- Copy the token — it won't be shown again

**Step 2: Configure git to store the token**

```bash
# Set up the credential helper to cache credentials
# "store" saves to ~/.git-credentials in plaintext (simple, persistent)
git config --global credential.helper store

# Now do a test operation that triggers auth — git will prompt for credentials
# Username: <their-github-username>
# Password: <paste the personal access token, NOT their GitHub password>
git ls-remote https://github.com/<their-username>/<any-repo>.git
```

After entering credentials once, they're saved and reused for all future operations.

**Alternative: cache helper (credentials expire from memory)**

```bash
# Cache in memory for 8 hours (28800 seconds) instead of saving to disk
git config --global credential.helper 'cache --timeout=28800'
```

**Alternative: set the token directly in the remote URL (per-repo)**

```bash
# Embed token in the remote URL (avoids credential prompts entirely)
git remote set-url origin https://<username>:<token>@github.com/<owner>/<repo>.git
```

**Step 3: Configure git identity**

```bash
# Required for commits — set name and email
git config --global user.name "Their Name"
git config --global user.email "their-email@example.com"
```

**Step 4: Verify**

```bash
# Test push access (this should work without any prompts now)
git ls-remote https://github.com/<their-username>/<any-repo>.git

# Verify identity
git config --global user.name
git config --global user.email
```

### Multi-Machine Workflow: GitHub + Bazzite (Your Name)

When the user asks to work on GitHub repos, use this three-step pattern:

1. **VPS (primary)** — do all git work on the VPS where Hermes runs
2. **Bazzite (mirror)** — when done (or when asked), mirror changes to the corresponding folder in the mirror folder on the secondary machine via Tailscale SSH/SCP
3. **Bazzite reachability check** — before attempting SCP, verify Bazzite is online:

```bash
# Check Tailscale reachability first
ping -c 1 -W 3 <mirror-machine-ip>

# If alive, SCP the repo folder (adjust path as needed)
scp -r ~/Developer/<repo-name> user@100.x.y.z:~/Documents/
```

> **Note**: Bazzite may be asleep/suspended between sessions. If ping fails, note it to the user — morning is fine for physical access. Tailscale daemon on Bazzite occasionally drops; the user can restart it with `ujust tailscale`.

### GitHub Account Mapping (Your Name)

- **Email**: `you@example.com`
- **GitHub username (working credential)**: `yourusername` — this is the account whose PAT is stored in `~/.git-credentials` on the VPS. Verified Jul 2025.
- **GitHub login (previously listed)**: `your-work-account` — may be an older/alternate org account; NOT the one with a stored credential. Verify before relying on.
- PAT scope needed: `repo` (full), `workflow`, `read:org`
- **Verified accessible repos** (Jul 2025): `yourorg/somerepo` ✅, `makeplane/plane` ✅ (public)
- **Verified NOT accessible**: `the company/the company-ai` ❌, `the agent/*` ❌ (token may lack scopes or no collaborator access)
- **Bazzite Documents path**: `~/Documents/` (confirm exact path via SSH on first connect)

### Option B: SSH Key Authentication

Good for users who prefer SSH or already have keys set up.

**Step 1: Check for existing SSH keys**

```bash
ls -la ~/.ssh/id_*.pub 2>/dev/null || echo "No SSH keys found"
```

**Step 2: Generate a key if needed**

```bash
# Generate an ed25519 key (modern, secure, fast)
ssh-keygen -t ed25519 -C "their-email@example.com" -f ~/.ssh/id_ed25519 -N ""

# Display the public key for them to add to GitHub
cat ~/.ssh/id_ed25519.pub
```

Tell the user to add the public key at: **https://github.com/settings/keys**
- Click "New SSH key"
- Paste the public key content
- Give it a title like "hermes-agent-<machine-name>"

**Step 3: Test the connection**

```bash
ssh -T git@github.com
# Expected: "Hi <username>! You've successfully authenticated..."
```

**Step 4: Configure git to use SSH for GitHub**

```bash
# Rewrite HTTPS GitHub URLs to SSH automatically
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

**Step 5: Configure git identity**

```bash
git config --global user.name "Their Name"
git config --global user.email "their-email@example.com"
```

---

## Method 2: gh CLI Authentication

If `gh` is installed, it handles both API access and git credentials in one step.

### Interactive Browser Login (Desktop)

```bash
gh auth login
# Select: GitHub.com
# Select: HTTPS
# Authenticate via browser
```

### Token-Based Login (Headless / SSH Servers)

```bash
echo "<THEIR_TOKEN>" | gh auth login --with-token

# Set up git credentials through gh
gh auth setup-git
```

### Verify

```bash
gh auth status
```

---

## Using the GitHub API Without gh

When `gh` is not available, you can still access the full GitHub API using `curl` with a personal access token. This is how the other GitHub skills implement their fallbacks.

### Setting the Token for API Calls

```bash
# Option 1: Export as env var (preferred — keeps it out of commands)
export GITHUB_TOKEN="<token>"

# Then use in curl calls:
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user
```

### Extracting the Token from Git Credentials

If git credentials are already configured (via credential.helper store), the token can be extracted:

```bash
# Read from git credential store
grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|'
```

### Helper: Detect Auth Method

Use this pattern at the start of any GitHub workflow:

```bash
# Try gh first, fall back to git + curl
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  echo "AUTH_METHOD=gh"
elif [ -n "$GITHUB_TOKEN" ]; then
  echo "AUTH_METHOD=curl"
elif [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
  export GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
  echo "AUTH_METHOD=curl"
elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
  export GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
  echo "AUTH_METHOD=curl"
else
  echo "AUTH_METHOD=none"
  echo "Need to set up authentication first"
fi
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `git push` asks for password | GitHub disabled password auth. Use a personal access token as the password, or switch to SSH |
| `remote: Permission to X denied` | Token may lack `repo` scope — regenerate with correct scopes |
| `fatal: Authentication failed` | Cached credentials may be stale — run `git credential reject` then re-authenticate |
| `ssh: connect to host github.com port 22: Connection refused` | Try SSH over HTTPS port: add `Host github.com` with `Port 443` and `Hostname ssh.github.com` to `~/.ssh/config` |
| Credentials not persisting | Check `git config --global credential.helper` — must be `store` or `cache` |
| Multiple GitHub accounts | Use SSH with different keys per host alias in `~/.ssh/config`, or per-repo credential URLs |
| `gh: command not found` + no sudo | Use git-only Method 1 above — no installation needed |
| `remote: Write access to repository not granted` (403) with `github_pat_` token | **Fine-grained PAT lacks "Contents: Read and write" permission.** Go to https://github.com/settings/personal-access-tokens → edit token → Repository permissions → Contents → Read and write. Or create a **classic PAT** (`ghp_` prefix) with `repo` scope instead — classic PATs don't need per-repo permission grants |
| API shows `push: true` but `git push` gets 403 | Same as above — the API reports the user's permissions, not the token's scopes. Fine-grained PATs need explicit "Contents: Read and write" even if the user has push access. Verify with: `curl -X PUT -H "Authorization: token <token>" https://api.github.com/repos/<owner>/<repo>/contents/test -d '{"message":"test","content":"dGVzdA=="}'` — if it returns "Resource not accessible by personal access token", the token needs more permissions |
