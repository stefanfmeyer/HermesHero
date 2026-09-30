---
name: github-multi-account-ssh
description: "Push to GitHub with multiple accounts via SSH host aliases when no API token is available. Also covers transferring repos between accounts (personal → org)."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, SSH, multi-account, authentication, git-remote]
    related_skills: [github-auth, github-repo-management]
---

# GitHub Multi-Account SSH Workflow

Create repos and push when the user has multiple GitHub accounts (e.g. personal + work) and no `GITHUB_TOKEN` / `gh` CLI auth is available. Uses SSH host aliases to pick the right key per account.

## When to use this skill

- `gh auth status` fails or `gh` is not installed
- No `GITHUB_TOKEN` env var, `.git-credentials`, or token in `~/.hermes/.env`
- **A token exists but cannot reach the target owner** (common with a personal
  token and an org repo — see the pre-flight section below; this is the case
  people skip and then get stuck on)
- User has SSH keys configured for multiple GitHub accounts in `~/.ssh/config`
- Need to create a new repo or push to an existing one under a specific account
- Publishing a repo that was ported out of a private one (audit it first)

## Prerequisites

The user must have SSH host aliases in `~/.ssh/config` like:

```
# Default account (e.g. work/the company)
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

# Personal account
Host github.com-personal
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_personal
    IdentitiesOnly yes
```

## Detect available auth methods

```bash
# Check SSH keys
ls ~/.ssh/id_*.pub 2>/dev/null

# Test which account each key authenticates as
ssh -T git@github.com 2>&1                    # default key
ssh -i ~/.ssh/id_ed25519_personal -T git@github.com 2>&1  # specific key

# Check if any API token exists
printenv GITHUB_TOKEN 2>/dev/null | head -c 5
grep "^GITHUB_TOKEN=" ~/.hermes/.env 2>/dev/null | head -c 5
cat ~/.git-credentials 2>/dev/null | head -c 20
```

If SSH works but no API token exists, use the SSH-only workflow below.

## A token can exist and still not reach the org (check this FIRST)

"A token exists" is not the same as "a token can create the repo you need". A
personal-account token commonly returns **404 on an organisation's repos**, even
while working perfectly for `/user`. Organisation membership is a separate grant
from authentication.

So the decision table is three checks, not one:

```bash
# 1. gh authenticated? (do NOT run interactive `gh auth login` from an agent
#    session — it blocks on a human prompt; verify then hand off instead)
gh auth status 2>&1 | head -3

# 2. Can the token actually reach the TARGET OWNER? Test a REPO endpoint —
#    /orgs/X returning 200 only proves the org is public, not that you have access.
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/repos/OWNER/REPO

# What the token CAN see (if the target owner is absent, you cannot create there)
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user/orgs \
  | python3 -c "import sys,json; print([o['login'] for o in json.load(sys.stdin)])"

# 3. Does the repo already exist? SSH answers this with no token at all.
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes" \
  git ls-remote git@github.com:OWNER/REPO.git >/dev/null 2>&1 \
  && echo "exists — SSH push will work" || echo "does NOT exist — creation needed"
```

| gh auth | token reaches owner | repo exists | Outcome |
|---|---|---|---|
| yes | — | — | Create + push |
| no | yes | no | `curl POST`, then push |
| no | **no** | no | **BLOCKED** — report it |
| no | no | yes | Push over SSH works fine |

**Run this pre-flight BEFORE doing the work when the task ends in "push to a
repo".** Doing a multi-hour port and only then discovering the repo can't be
created wastes the whole session's deliverable. If blocked: do the work, commit
locally, and state the blocker plus the two unblock paths (user runs
`gh auth login`, or user creates the empty repo). Then the push is one command.

Once the user creates it, `git ls-remote` returns non-empty and:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes" git push -u origin main
```

## Verify the push independently — don't trust the push output

`git push` reporting success is a claim from the local client. Confirm the remote
actually holds the content, especially on a first push to a brand-new repo:

```bash
git fetch origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] && echo MATCH || echo MISMATCH
git log --oneline origin/main..HEAD | wc -l    # 0 = fully pushed

# Strongest: clone fresh and inspect the working tree. The SHA comparison alone
# passes even if a .gitignore silently excluded the directory you meant to ship.
git clone -q git@github.com:OWNER/REPO.git /tmp/verify-clone
cd /tmp/verify-clone && find . -type f -not -path './.git/*' | wc -l
git cat-file -e origin/main:<critical-file> && echo present
```

Then confirm what must NOT be there — gitignored paths and env files:

```bash
git ls-tree -r --name-only origin/main | grep -c '^\.hermes/'   # e.g. plan docs: must be 0
git ls-tree -r --name-only origin/main | grep -E '^\.env'       # inspect each one
```

## Pre-push audit when publishing code out of a private repo

**Run `scripts/preflight-public-repo-audit.sh` (in this skill) from the repo root
before the first push** — it scans the tracked tree for internal infrastructure,
credential-shaped content, provider API keys, JWT literals with their decoded
`role` claim, env files, and gitignored directories that should not be on the
remote. Exit code 1 means something actionable was found, so it can gate a push.

Publishing to a public repo turns every committed file world-readable. When
*porting* code from a private repo (rather than writing fresh), internal context
travels with it in places a code review won't catch:

```bash
grep -rniE "tailscale|tailnet|100\.[0-9]+\.[0-9]+\.[0-9]+|workstation|<internal-host>" \
  --include='*.ts' --include='*.tsx' --include='*.py' --include='*.md' \
  --include='*.json' --include='*.sh' --include='*.yml' . | grep -v node_modules

grep -rniE "id_ed25519|\.ssh/|deploy_key|private key|passwd|secret *[:=]" \
  --include='*.ts' --include='*.py' --include='*.md' --include='*.sh' . | grep -v node_modules
```

Two traps a naive scan misses:

1. **Comments carry internal context.** A comment copied from a private repo can
   name an internal hostname or tailnet URL ("served over plain HTTP at
   `http://<internal-host>:3199`") while the code itself is clean. Grep comments —
   the whole file is committed.
2. **Scripts hardcode machine-local paths.** A deploy script defaulting to
   `~/.ssh/<specific-key-name>` leaks which key is used and breaks for everyone
   else. Require it from the environment and fail loudly:

   ```bash
   if [[ -z "${DEPLOY_KEY:-}" ]]; then
     echo "DEPLOY_KEY must be set to the deploy SSH key path." >&2
     exit 1
   fi
   ```

**Decode any JWT-shaped literal before judging it** — the prefix tells you
nothing:

```bash
grep -rhoE 'eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}' . 2>/dev/null | sort -u | while read t; do
  p=$(echo "$t" | cut -d. -f2); pad=$(( (4 - ${#p} % 4) % 4 ))
  printf '%s' "$p$(printf '=%.0s' $(seq 1 $pad))" | base64 -d 2>/dev/null \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print('role:',d.get('role'),'iss:',d.get('iss'))"
done
```

A Supabase key with `role: anon` is **designed** to be public (RLS-constrained,
the same key the web app ships) — safe to commit, and its presence is not a leak.
A `service_role` key bypasses RLS entirely and must never ship. Only the decoded
claim distinguishes them.

## Creating a new repo without an API token

You cannot create a repo via the GitHub API without a token. Instead:

1. **Ask the user to create the empty repo on GitHub** (give them the exact name and account to use).
2. **Verify the remote repo exists** and is empty:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal -o IdentitiesOnly=yes" \
  git ls-remote git@github.com:yourusername/my-repo.git
# Empty repo: exit 0, no output. Non-empty: lists refs.
```

3. **Init local repo, set identity, add remote, commit, push:**

```bash
cd /path/to/project
git init -b main

# Set per-repo identity (NOT global — different repos use different identities)
git config user.name "yourusername"
git config user.email "you@example.com"

# Use the SSH host alias from ~/.ssh/config in the remote URL
git remote add origin git@github.com-personal:yourusername/my-repo.git

git add -A
git commit -m "Initial commit: description of project"

# Push — GIT_SSH_COMMAND ensures the right key even if ~/.ssh/config is ambiguous
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal -o IdentitiesOnly=yes" \
  git push -u origin main
```

## Pushing to an existing repo

Same pattern — just skip `git init` and `git remote add` if already set up:

```bash
cd /path/to/existing-repo
git config user.name "yourusername"
git config user.email "you@example.com"

git add -A
git commit -m "descriptive message"

GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal -o IdentitiesOnly=yes" \
  git push origin main
```

## Key rules

1. **Always use the SSH host alias in the remote URL** (`git@github.com-personal:...` not `git@github.com:...`). The default `Host github.com` block may point to a different account's key.

2. **Set git identity per-repo** (`git config user.name` without `--global`) when the user has multiple accounts. Never assume the global identity is correct.

3. **Use `GIT_SSH_COMMAND` to override the key** for operations that might not respect `~/.ssh/config` Host blocks (e.g. `git ls-remote`, some CI environments). Belt-and-suspenders alongside the host alias.

4. **Verify with `ssh -T`** before pushing to confirm which account the key authenticates as:
   ```bash
   ssh -i ~/.ssh/id_ed25519_personal -T git@github.com 2>&1
   # Expected: "Hi yourusername! You've successfully authenticated..."
   ```

## Discovering a user's repo when the name is unknown

The user may refer to a site by domain while the repo has a different or capitalized name (e.g. `my-portfolio.com` → `yourusername/my-portfolio`). Before asking:

1. List the account's repos: `curl -s "https://api.github.com/users/<user>/repos?per_page=100&sort=updated"` (public only — a missing repo may just be private).
2. Probe candidate names with the correct SSH key: `GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal" git ls-remote git@github.com:<user>/<Guess>.git`.
3. If a repo 404s with the default key, ALWAYS retry with the personal key before concluding it doesn't exist (see Pitfalls table).
4. When asking the user, ask for the exact repo URL — one round-trip beats guessing sprees.

## Transferring a repo between accounts (personal → org)

When the user wants to move a repo from their personal GitHub account to an org account (e.g. yourusername/pragmatic → the company/pragmatic), the code stays the same — only the remote and identity change.

1. **Create the empty target repo** on GitHub (user does this in the UI, or via API if a token is available).
2. **Update the remote URL** to use the destination account's SSH host alias:
   ```bash
   cd /path/to/repo
   git remote set-url origin git@github.com-the company:the company/pragmatic.git
   ```
3. **Verify the git identity** is correct for the destination account:
   ```bash
   git config user.name "Your Name"
   git config user.email "you@example.com"
   ```
4. **Push to the new remote:**
   ```bash
   git push -u origin main
   ```
5. **Verify** the old remote is gone and the new one is correct:
   ```bash
   git remote -v
   ```

No `git filter-branch` or history rewrite is needed — the commits stay the same, only the remote changes. The old personal repo can be archived or deleted on GitHub after confirming the transfer worked.

## Generating a key for the user (CI deploy keys, extra accounts)

When you generate a keypair on the user's behalf, two rules that are not negotiable and one that is
just good hygiene:

1. **A private key never goes into a chat channel** — not as text, not as a file attachment, not
   base64. A chat attachment URL is not scoped to the requester, does not expire, and reaches
   everyone with read access to the channel; the key often opens a `sudo`-capable shell on a
   production host. Terminal tooling strips private keys from output, and encoding around that guard
   is defeating the guard. This holds even when the user asks directly and repeats the ask, and even
   after they clarify that a second handle in the thread is also them — identity corrections do not
   change who can read the channel or how long the artifact lives.
   Deliver by a path that does not pass through chat instead:

   ```bash
   scp user@host:~/.git/<repo>-ci-deploy.key .                       # pull over existing access
   gh secret set <NAME> --repo owner/repo < <keyfile>                # set the secret, never displayed
   ```

   Say no once, plainly, and put the working alternative in the same message. If they insist the
   channel is private, ask them to confirm the specific people who should hold that access rather
   than inferring it.

2. **Generate a dedicated key per purpose — never reuse the operator's personal key.** Automation
   should be revocable without taking away the human's access. Install the public half under a
   recognisable comment, idempotently, after backing up `authorized_keys` (a mistake there locks you
   out of the box):

   ```bash
   cp -a ~/.ssh/authorized_keys ~/.ssh/authorized_keys.bak-$(date +%Y%m%d-%H%M%S)
   grep -qF "<repo>-ci-deploy" ~/.ssh/authorized_keys || printf '%s\n' "$PUBKEY" >> ~/.ssh/authorized_keys
   ```

3. **Verify the key authenticates before relying on it**, and offer deletion of the plaintext copy
   once it has been installed as a secret — rotation is a new pair plus a swapped `authorized_keys`
   line. If a key genuinely must be shared, reissue it as a **forced-command** key
   (`command="…",restrict`) so a leaked copy can only trigger the deploy, not open a shell.

For the full CI/CD side of this (workflow shape, version assertions, rehearsing a workflow locally),
see the `github-actions-ssh-deploy` skill.

## Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| `remote: Permission to X denied` | Remote URL uses default key (wrong account) | Use host alias in remote URL: `git remote set-url origin git@github.com-personal:user/repo.git` |
| Push goes to wrong account's repo | `~/.ssh/config` `Host github.com` points to default key | Use the alias (`github.com-personal`) in the remote URL |
| `git config --global` overrides per-repo identity | Global config set for the other account | Always set per-repo: `git config user.name` (no `--global`) |
| `git ls-remote` uses wrong key | Doesn't read `~/.ssh/config` Host block | Set `GIT_SSH_COMMAND="ssh -i ~/.ssh/specific_key -o IdentitiesOnly=yes"` |
| `Repository not found` on a repo that visibly exists | Repo is private and the DEFAULT key authenticates as the other account | Retry with the personal key explicitly: `GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal" git ls-remote git@github.com:owner/repo.git`. Proven case: `yourusername/my-portfolio` 404'd via default key but cloned instantly with the personal key. Don't conclude "repo doesn't exist" after one failed attempt — test both keys before asking the user. |
| Cloning a private repo fails or hangs asking for credentials | Wrong key for the account that owns the repo | Over SSH: `Repository not found`. Over HTTPS with no terminal prompt: hangs with `could not read Username`. Both mean key/account mismatch — retry with `GIT_SSH_COMMAND="ssh -i <key>" git clone ...` before asking the user. Verified 2026-09-11: `yourusername/my-portfolio` cloned first try once the personal key was passed explicitly. |
| `gh repo create` fails — not authenticated | No `gh auth login` and no `GITHUB_TOKEN` | Use the SSH-only workflow: user creates empty repo, you push |

## the user's specific setup

See memory entry for account details. Key mapping:
- `id_ed25519` = the company account (default `Host github.com`)
- `id_ed25519_personal` = personal yourusername account (`Host github.com-personal`)

Personal commits: `yourusername <you@example.com>`
the company commits: `Your Name <you@example.com>`