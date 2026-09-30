---
name: vps-file-editing-workflow
description: Edit files on a remote VPS (via SSH/SCP) using local tools. Download → patch locally → verify → upload. Avoids all shell quoting issues with heredocs and python -c over SSH.
---

# VPS File Editing Workflow

Edit Python or other code files on a remote VPS using local tools to avoid shell quoting problems.

## When to Use

When you need to edit files on a remote VPS (via SSH) and the edits are complex enough that shell escaping becomes problematic. Specifically when:
- The file contains Python triple-quoted strings
- The edits involve complex f-strings or nested quotes
- Heredocs or `python3 -c` over SSH fail due to quoting
- The `patch` tool (local) works cleanly but SSH heredocs mangle the content

## Workflow

### Step 1: Download to Local

```bash
scp openclaw-vps:/home/node/.openclaw/workspace/CCE-ENGINE-VPS/pipeline/pipeline_run.py /tmp/pipeline_run.py.bak
echo "Downloaded ($(wc -c < /tmp/pipeline_run.py.bak) bytes)"
```

### Step 2: Read the Target Section

Use `read_file` with `offset` and `limit` to find exact line ranges:

```bash
grep -n "def _exact_method_name" /tmp/pipeline_run.py.bak
# Then read with:
read_file(path="/tmp/pipeline_run.py.bak", offset=<line-5>, limit=<50>)
```

### Step 3: Apply Patches Locally with `patch` Tool

```python
patch(
    new_string="""    def _new_method(self):
        \"\"\"New docstring.\"\"\"
        pass""",
    old_string="""    def _old_method(self):
        \"\"\"Old docstring.\"\"\"
        pass""",
    path="/tmp/pipeline_run.py.bak"
)
```

**Important**: Use the `patch` tool (NOT terminal sed/python), because:
- It handles all quoting correctly
- Returns a unified diff showing exactly what changed
- Runs linting checks automatically
- No shell escaping needed

### Step 4: Verify Syntax

```bash
python3 -c "import py_compile; py_compile.compile('/tmp/pipeline_run.py.bak', doraise=True); print('Syntax OK')"
```

### Step 5: Upload Back to VPS

```bash
scp /tmp/pipeline_run.py.bak openclaw-vps:/home/node/.openclaw/workspace/CCE-ENGINE-VPS/pipeline/pipeline_run.py
echo "Uploaded"
```

### Step 6: Verify on VPS

```bash
ssh openclaw-vps "python3 -c \"
import sys; sys.path.insert(0, '/home/node/.openclaw/workspace/CCE-ENGINE-VPS/pipeline')
import pipeline_run
for m in ['_new_method']:
    exists = hasattr(pipeline_run.PipelineEngine, m)
    print('[OK]' if exists else '[MISSING]', m)
\""
```

## Syncing a VPS Repo That's Behind + Has Local Changes

When the VPS repo is BOTH behind `origin/main` AND has uncommitted changes:

```bash
# 1. Check what's happening
ssh openclaw-vps "cd /path/to/repo && git status && git remote -v"
```

**Two cases:**

**Case A — Uncommitted changes MATCH the origin commits (already applied upstream):**
```bash
ssh openclaw-vps "cd /path/to/repo && git stash && git pull origin main --rebase && git stash pop"
# git auto-detects patch-already-applied and drops the stash cleanly
```

**Case B — Uncommitted changes are genuinely new and need pushing:**
```bash
# Pull the behind commits first, then commit and push
ssh openclaw-vps "cd /path/to/repo && git pull origin main && git add -A && git commit -m 'fix: desc' && git push origin main"
```

**Verification after sync:**
```bash
ssh openclaw-vps "cd /path/to/repo && git log --oneline -3"
# Should match what you see on GitHub
```

**Key insight**: `git pull --rebase` handles the case where uncommitted changes are identical to what would be pulled — it automatically discards the redundant stash as "patch already applied."

### Method 2: Python Patch Script (SCP → Execute) — Best for Complex Strings

When edits involve Python dict literals, f-strings, triple-quoted strings, or complex Python data structures, write the patch script as a `.py` file locally, SCP it to the VPS, then execute it with `python3`. This avoids ALL shell quoting issues.

**Step 1**: Write the Python patch script to a local file:
```python
# /tmp/fix_script.py (on your local machine)
filepath = '/home/node/CCE-ENGINE-VPS/skills/internal_link_mapper/scripts/internal_link_mapper.py'
with open(filepath, 'r') as f:
    content = f.read()

old = '''    # Reject anchors < 12 chars
    if best_anchor and len(best_anchor) < 12:
        best_anchor = None'''
new = '''    # Reject anchors < 12 chars
    if best_anchor and len(best_anchor) < 12:
        print(f"    ~ Skipping {best_match} -- anchor too short ({len(best_anchor)} chars)")
        best_anchor = None'''

if old in content:
    content = content.replace(old, new, 1)
    print('PATCH OK')
else:
    print('PATCH MISSING - check context')

with open(filepath, 'w') as f:
    f.write(content)
```

**Step 2**: SCP to VPS and execute:
```bash
scp /tmp/fix_script.py openclaw-vps:/tmp/fix_script.py
ssh openclaw-vps "python3 /tmp/fix_script.py"
```

**Step 3**: Verify:
```bash
ssh openclaw-vps "python3 -c \"import ast; ast.parse(open('/home/node/...').read())\" && echo 'SYNTAX OK'"
```

**Why this works**: The patch script itself is a plain text file. SCP transfers it byte-for-byte with no shell interpretation. Running with `python3 /tmp/script.py` executes it directly — no shell quoting, no escaping, no heredoc issues.

### Method 3: Download → Edit Locally → Upload (for text-based edits)

For simple text changes without complex Python structures:
```bash
# Download
scp openclaw-vps:/path/to/file.py /tmp/file.py.bak

# Edit locally with patch tool or read_file + write_file
# ... make changes ...

# Upload
scp /tmp/file.py.bak openclaw-vps:/path/to/file.py
```

**Verification after upload:**
```bash
ssh openclaw-vps "python3 -c \"import ast; ast.parse(open('/path/to/file.py').read())\" && echo 'SYNTAX OK'"
```

## Why Not `python3 - << 'HEREDOC'` Over SSH?

Heredocs over SSH (`ssh host 'python3 - << HEREDOC'`) mangle:
- Triple-quoted Python strings
- f-string expressions like `{len(x) if x else 0}`
- Unicode and em dashes

**Symptoms**: `SyntaxError: unexpected character` or shell `syntax error near token (`

**In this session**: Multiple patches to `internal_link_mapper.py` failed with `AssertionError: PATCH 5 old string not found` because the heredoc approach silently mangled the assertion strings. Only writing to a local `.py` file, SCPing it, and executing it worked reliably.

## ⚠️ Gotcha: `r'\b'` Raw Strings Get Corrupted to Backspace Bytes

When a Python patch script (written to disk by the agent) uses `r'\b'` for regex word boundaries, the `\b` can be stored as a **literal backspace byte (0x08)** instead of the two-character sequence `\` + `b`. This silently breaks all regex word-boundary patterns — `re.sub(r'\bmaximize\b', ...)` will never match anything.

**Symptoms**: Regex replacement works when tested in isolation but silently fails in the actual function. Function returns input unchanged.

**Fix**: Use explicit string concatenation instead of raw strings for word boundaries:
```python
# WRONG — \b may corrupt to backspace byte 0x08:
pattern = r'\b' + re.escape(us) + r'\b'

# CORRECT — explicit backslash:
pattern = '\\b' + re.escape(us) + '\\b'
```

**Detection**: Open the file in a Python script and scan for `0x08` bytes:
```python
with open(filepath, 'rb') as f:
    data = f.read()
for i, b in enumerate(data):
    if b == 0x08:
        print("Corrupt byte at position", i)
```

**Repair**: Replace all `0x08` bytes with the two-byte sequence `b'\\b'`:
```python
with open(filepath, 'rb') as f:
    data = bytearray(f.read())
data = data.replace(b'\x08', b'\\b')
with open(filepath, 'wb') as f:
    f.write(data)
```

## Vercel Serverless Deploy Debugging

### First check: is there an active deployment?
```bash
curl -sI https://<project>.vercel.app/ | grep x-vercel-error
# DEPLOYMENT_NOT_FOUND = no successful deployment ever exists
# Blank 404 from function = deployment exists but routing is broken
```

### Zero deployments in dashboard (not even failures)
Common causes when the Vercel dashboard shows no deployments at all:
1. **`package.json` missing `vercel-build` script** — Vercel's "Other" framework preset runs `npm run vercel-build` as part of every deployment. If that script is missing, the build step fails with no visible error and the deployment is silently skipped.
2. **Vercel team plan billing block** — some team plans require a credit card on file and build machine config. If there's a billing banner or "paused" state in the dashboard, deployments are blocked until billing is sorted.
3. **Git trigger not firing** — even with repo connected, if the Git webhook isn't registered with GitHub, pushes don't trigger deploys. Reconnect the repo in Settings → Git to force webhook re-registration.
4. **Production branch not set** — ensure Settings → Git → Production Branch = main.

### Fix for missing vercel-build
```json
"scripts": {
  "vercel-build": "echo 'No build step needed'",
  "test": "..."
}
```

### Routing 404 after a successful deploy
If the deployment completes but all routes return 404: the `vercel.json` is missing the `rewrites` array. Add:
```json
"rewrites": [
  { "source": "/webhook/conversifi", "destination": "/api/webhook/conversifi" }
]
```

### Auth headers must be lazy in serverless
Module-level const assignment evaluates env vars at cold-start time, before Vercel injects secrets:
```js
// WRONG — headers set to undefined at module load
const headers = { Authorization: `Token token=${process.env.X}` };

// CORRECT — computed per request at runtime
function getHeaders() {
  return { Authorization: `Token token=${process.env.X}` };
}
// All axios calls: { headers: getHeaders() }
```

### Dynamic import bug in email-sequences.js
Never use `await import('axios')` inside an async function when axios is already imported at the top of the file. The dynamic import resolves asynchronously in a different module context in serverless runtimes. Use the top-level import instead.

## VPS Has No Git

On some VPS deployments (e.g. `/home/node/CCE-ENGINE-VPS/` on openclaw-vps), git is not installed. To still commit changes:

1. **Clone the repo locally** (your Mac has git):
   ```bash
   cd /tmp && git clone https://github.com/neon-gorilla-official/CCE-ENGINE-VPS.git cce-engine-vps-git
   ```

2. **SCP the changed files** from the VPS to the local clone:
   ```bash
   scp openclaw-vps:/home/node/CCE-ENGINE-VPS/skills/section_expander/scripts/section_expander.py /tmp/cce-engine-vps-git/skills/section_expander/scripts/
   scp openclaw-vps:/home/node/CCE-ENGINE-VPS/pipeline/pipeline_run.py /tmp/cce-engine-vps-git/pipeline/
   ```

3. **Commit and push** from the local clone:
   ```bash
   cd /tmp/cce-engine-vps-git
   git add <changed files>
   git commit -m "fix: description"
   git push origin main
   ```

4. **If remote is ahead** (another push happened), pull first with rebase:
   ```bash
   cd /tmp/cce-engine-vps-git && git pull --rebase origin main && git push origin main
   ```

5. **Sync back to VPS** by SCPing the committed files:
   ```bash
   scp /tmp/cce-engine-vps-git/pipeline/pipeline_run.py openclaw-vps:/home/node/CCE-ENGINE-VPS/pipeline/
   ```

## Backup Strategy

Always keep `.bak` copies locally before uploading:
```bash
scp host:/path/file /tmp/file.bak
```
If upload corrupts, `scp /tmp/file.bak host:/path/file` restores instantly.
