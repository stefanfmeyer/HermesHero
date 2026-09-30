---
name: cross-platform-npm-scripts
description: Build npm `package.json` scripts and `scripts/*.js` helpers that work on Windows PowerShell, macOS/Linux bash, and WSL. Covers the `cd X && ...` PowerShell pitfall, the python3 vs python detection problem, the process.execPath pattern for spawning node, npm-spawned background children that escape pidfiles, and cross-platform PID/process kill. Use whenever a project has a `package.json` with start/test scripts and a non-Windows dev machine has been the only environment tested — the moment a Windows user clones, the bugs surface.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [npm, cross-platform, windows, powershell, bash, node, process-management, packaging]
    related_skills: [subagent-large-project-pattern, hermes-agent-skill-authoring]
triggers:
  - "make this npm script work on Windows"
  - "PowerShell does not support &&"
  - "script works on Mac but not Windows"
  - "how do I run this cross-platform"
  - "Python command not found on Windows"
  - "cd X && python3 fails on Windows"
  - "postinstall recursion in npm workspaces"
  - "npm install hangs after the same script runs N times"
  - "npm error command C:\\Windows\\system32\\cmd.exe /d /s /c npm install"
---

# Cross-Platform npm Scripts

When a project has `package.json` scripts or `scripts/*.js` helpers, the **default assumption** is "this works on macOS/Linux because that's where I tested it." That assumption fails the moment a Windows user clones the repo. This skill captures the recurring failure modes and the working patterns.

## The `cd X && ...` PowerShell Trap

**The most common cross-platform bug.** macOS/Linux bash treats `&&` as a shell operator. PowerShell does **not** — `&&` in PowerShell is a pipeline-chain operator, not a command-chain operator, and it works on **cmdlets**, not on `cd` (which is `Set-Location` in PowerShell, an alias). What looks fine in bash will fail in PowerShell.

```jsonc
// BAD — works in bash, fails in PowerShell
"start:parser": "cd packages/parser && python3 -m uvicorn parser_service:app --port 8000"
"start:api":    "cd packages/api && node server.js"
```

What the Windows user sees:

```
npm error code 1
npm error file C:\...\package.json
npm error > cd packages\parser && python3 -m uvicorn ...
npm error ^
npm error 'cd' is not recognized as an internal or external command
```

(or worse, PowerShell silently runs only the first part of the chain and the second never executes.)

**Fix A: write a Node launcher, set `cwd` via `spawn`.**

Create `scripts/start-one.js`:

```js
#!/usr/bin/env node
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const WHICH = process.argv[2];
if (!WHICH) { console.error("usage: start-one.js <service>"); process.exit(2); }

const isWin = process.platform === "win32";
const python = process.env.PYTHON || (isWin ? "python" : "python3");

const SERVICES = {
  parser: { cmd: python, args: ["-m", "uvicorn", "parser_service:app", "--host", "127.0.0.1", "--port", "8000"], cwd: join(ROOT, "packages/parser") },
  api:    { cmd: process.execPath, args: ["server.js"], cwd: join(ROOT, "packages/api") },
  ui:     { cmd: "npx", args: ["--no-install", "vite", "--host", "127.0.0.1"], cwd: join(ROOT, "packages/review-ui") },
};

const svc = SERVICES[WHICH];
if (!svc) { console.error(`unknown service: ${WHICH}`); process.exit(2); }

const child = spawn(svc.cmd, svc.args, { cwd: svc.cwd, stdio: "inherit", env: process.env });
process.on("SIGINT",  () => { if (!child.killed) child.kill("SIGINT"); });
process.on("SIGTERM", () => { if (!child.killed) child.kill("SIGTERM"); });
child.on("exit", (code) => process.exit(code ?? 0));
```

Then in `package.json`:

```jsonc
"start:parser": "node scripts/start-one.js parser",
"start:api":    "node scripts/start-one.js api",
"start:ui":     "node scripts/start-one.js ui"
```

This works on PowerShell, bash, and WSL unchanged.

**Fix B: if you must use a string, use `npx cross-env` or `npm-run-all`.** Slower, requires an extra dep, but works without writing a script. Use only for trivial one-liners; prefer Fix A for anything that spawns a process.

**Fix C: cross-platform `&` is also a trap.** PowerShell `&` is the call operator, not background-AND. Don't try to be clever with shell operators across platforms — use Node.

## The `python3` Problem

`python3` is the macOS/Linux binary. On Windows:
- Official Python installer: `python` (and the launcher `py`)
- Microsoft Store Python: `python` (no `python3` symlink)
- WSL: `python3` (works inside WSL, fails in Windows native shells)

**Detection pattern:**

```js
const isWin = process.platform === "win32";
const python = process.env.PYTHON || (isWin ? "python" : "python3");
```

Allow override via `PYTHON` env var for the rare case where someone needs a specific version on Mac (e.g. system Python 2 vs Homebrew Python 3).

**Do not** hardcode `py` (Python launcher) — it's Windows-only, and users on Mac who don't have any Python install will get a confusing "command not found" instead of an actionable "install Python 3.10+".

### The dev-machine venv path trap (CI-only failure)

`isWin ? "python" : "python3"` is not enough when the script was written where a **virtualenv** was active. Hardcoding the venv interpreter is the same bug class as hardcoding `python3`, one level worse — the path is machine-specific, not OS-specific:

```js
// BAD — exists only on the dev machine
cmd: process.env.PYTHON || "$HOME/.hermes/hermes-agent/venv/bin/python3",
```

On a CI runner that path does not exist. `spawnSync` returns `{status: null, error: {code: 'ENOENT'}}`, which a naive `r.status === 0 ? pass++ : fail++` counts as a **failed test group**. The result is the worst kind of failure to debug: **CI reports "6 passed, 1 failed" while the identical commit is 8/8 locally**, and nothing says "interpreter missing". The group count itself is the tell — count your groups, don't just read the pass/fail line:

```bash
grep -c "name:" scripts/run-tests.js   # how many groups SHOULD run
```

**Fix: resolve the interpreter at runtime by probing, not by guessing.**

```js
function resolvePython() {
  const candidates = [
    process.env.PYTHON,
    "$HOME/.hermes/hermes-agent/venv/bin/python3",  // dev-machine venv
    "python3",
    "python",
  ].filter(Boolean);

  let lastExisting = null;
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, ["-c", "import pytest"], { stdio: "ignore" });
    if (probe.status === 0) return cmd;          // exists AND has the dep
    if (!probe.error) lastExisting = cmd;        // exists, dep missing
  }
  // Fall back to something that exists so the group fails with a REAL error
  // (e.g. "No module named pytest") rather than a mystery ENOENT.
  return lastExisting || "python3";
}
```

Key properties: probe for the *dependency* (`import pytest`), not just existence, so the first candidate that can actually do the job wins; keep the dev-machine path as a candidate (it's faster and correct locally); and **never return a path that doesn't exist** — an ENOENT is unattributable, whereas a real "module not found" tells the next agent exactly what to install.

**A CI workflow also needs the interpreter provisioned.** Adding `actions/setup-python` + `pip install <test deps>` is part of the fix — check whether the workflow ever installed Python at all before assuming the script is the only problem. Install only the deps the selected test files reach: lazy `import anthropic` inside a function means `pytest + pydantic` may be sufficient, and full `requirements.txt` is much slower.

**Verifying the fix without a CI runner you can log into:** the job is to prove the script no longer depends on a path that only you have. Mask the dev-machine path in a mount namespace and run the suite with a bare `PATH` pointing at a clean venv:

```bash
unshare -rm sh -c 'mount --bind /dev/null $HOME/.hermes/hermes-agent/venv/bin/python3 \
  && env -i PATH=/tmp/citest/bin:/usr/bin:/bin HOME=/tmp/fakehome node scripts/run-tests.js'
```

Pitfall: a venv is only a venv if `pyvenv.cfg` sits beside the binary, so a bare **symlink** to the venv python breaks it (`No module named pytest` on a python that has pytest). Point `PATH` at the venv's real `bin/` directory instead of symlinking one file.

If the repo is private and you have no `gh` auth, you cannot read the CI log. Say so, then reproduce the failing condition locally (above) rather than guessing at the cause from the pass/fail count alone.

## The `process.execPath` Pattern for Node

Don't hardcode `"node"` in a script that spawns other node processes. Use `process.execPath` — the absolute path of the currently-running node binary. This means:

- Works under nvm, fnm, volta, asdf, nvs (whatever spawned this script has the right node)
- Works with custom node builds
- Avoids the Windows "where's node" problem if `node` isn't on PATH

```js
const child = spawn(process.execPath, ["server.js"], { cwd: ..., stdio: "inherit" });
```

## Background Processes: npm-Spawned Children Escape Your Pidfiles

When you spawn a process from a Node script and write its PID to a file, the PID you captured is the **direct child** — but if that child is `npm` (which in turn spawns `node` running your real service), the actual service is a **grandchild**, not a child. The pidfile tracks npm; killing it on `stop` does not kill the underlying service.

**Pattern that bit us (a real project 2026-07-02):**
- `start-all.js` spawns `npm run dev` to launch Vite
- npm forks vite → esbuild → etc.
- pidfile holds npm's PID
- `stop-all.js` reads pidfile, kills npm — but Vite keeps running because the npm parent was the only thing killed
- Next day: orphan Vite process eating CPU, `make status` says "all stopped"

**Fixes:**

1. **Don't spawn via npm when you can spawn the binary directly.** `node` and `npx --no-install` are the right tools. `npm run` is a wrapper, not a process you want as a long-lived child.

2. **`detached: true` + `setsid` (POSIX) or `windowsHide` (Windows).** On POSIX, `spawn(cmd, args, { detached: true })` puts the child in a new process group so killing the parent doesn't cascade. On Windows, use `windowsHide: true` and accept that you'll have to find children via `wmic process where ParentProcessId=<pid> get ProcessId` or `taskkill /T /F /PID <pid>`.

3. **Process group kill on POSIX:** `process.kill(-pgid, 'SIGTERM')` (note the `-` prefix). Requires `spawn(..., { detached: true })` so a new pgid is created.

4. **Port-based fallback.** If pidfile kill fails, fall back to "find what owns port 8000 and kill it":

   ```js
   import { execSync } from "node:child_process";
   function killByPort(port) {
     try {
       if (process.platform === "win32") {
         execSync(`for /f "tokens=5" %a in ('netstat -aon ^| findstr :${port}') do taskkill /F /PID %a`, { stdio: "ignore" });
       } else {
         execSync(`fuser -k ${port}/tcp 2>/dev/null || lsof -ti:${port} | xargs -r kill -9`, { stdio: "ignore" });
       }
     } catch {}
   }
   ```

## Cross-Platform Status Checks (Without bash/curl/ss)

Avoid `scripts/status.sh` — it depends on `bash`, `ss`/`netstat`, `curl`, `pgrep`. All available on macOS/Linux, all require separate install on Windows. Write a Node version using built-ins:

```js
#!/usr/bin/env node
import { existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

function processAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

async function fetchCode(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
    return res.status;
  } catch { return 0; }
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOGS = join(__dirname, "..", ".logs");

for (const name of ["parser", "api", "ui"]) {
  const pidfile = join(LOGS, `${name}.pid`);
  if (!existsSync(pidfile)) { console.log(`  ${name}: not running`); continue; }
  const pid = parseInt(readFileSync(pidfile, "utf8").trim(), 10);
  console.log(`  ${name}: ${pid && processAlive(pid) ? `up (pid ${pid})` : "dead (stale pidfile)"}`);
}

for (const [label, url] of [["Parser", "http://127.0.0.1:8000/health"], ["API", "http://127.0.0.1:3000/health"]]) {
  const code = await fetchCode(url);
  console.log(`  ${label}: ${code === 200 ? "OK" : code === 0 ? "down" : `HTTP ${code}`}`);
}
```

`fetch()` is built into Node 20+ (no `node-fetch` dep). `process.kill(pid, 0)` works on every platform for liveness checks. `AbortSignal.timeout()` is also built-in.

## The `postinstall` Recursion Trap (npm workspaces)

**Tempting but DANGEROUS — DO NOT DO THIS:**

```jsonc
// BAD — causes infinite recursion
"postinstall": "npm install --workspaces --include-workspace-root"
```

The reasoning sounds fine: "I want a single `npm install` at the root to also install all workspace packages." But this **recurses forever** because:

1. User runs `npm install` at the repo root
2. npm resolves the workspace graph, installs each workspace's deps into root `node_modules`
3. After the install, npm fires the `postinstall` script
4. The postinstall runs `npm install --workspaces --include-workspace-root` — which is exactly the same command the user just ran
5. That nested install fires postinstall again
6. Repeat until npm gives up (or hits the user's patience limit)

The error the user sees (a real project 2026-07-02, Windows PowerShell):

```
npm error code 1
npm error path C:\Users\youruser\Documents\my-project
npm error command failed
npm error command C:\Windows\system32\cmd.exe /d /s /c npm install --workspaces --include-workspace-root

npm error code 1
npm error path C:\Users\youruser\Documents\my-project
npm error command failed
... (8 copies, each ~1s apart, each triggering the next)
```

Note the `C:\Windows\system32\cmd.exe /d /s /c npm install...` — that's npm 10+ delegating to `cmd.exe` on Windows to run the postinstall, and each call recursively re-runs the same postinstall.

**Why it SEEMS like a good idea:** in a workspace repo, `npm install` at the root *does* install all workspace deps by default. The postinstall is **redundant**. Plain `npm install` already does what the postinstall was trying to do.

**The fix:** just remove the `postinstall`. Plain `npm install` is enough. If you need a lockfile, commit the root `package-lock.json` that npm generates (it covers the full dep graph including workspace packages).

**Test it before shipping:** if you have a `postinstall` in a workspace repo, run `npm install` once locally and check that **only one** install command appears in the output. If you see the same install command run multiple times, you have the recursion.

```bash
# Quick local check
cd /path/to/repo && rm -rf node_modules package-lock.json
npm install 2>&1 | grep -c "npm install --workspaces"
# Should print "0" or "1" — anything higher means recursion
```

## Makefile + npm Scripts: Both, Not Either/Or

A `Makefile` is great for the dev's own machine (macOS/Linux) but useless on Windows without WSL or chocolatey-installing make. **Always also provide a `package.json` with matching scripts.** Pattern:

```jsonc
"scripts": {
  "start":   "node scripts/start-all.js",
  "stop":    "node scripts/stop-all.js",
  "status":  "node scripts/status.js",
  "test":    "node scripts/run-tests.js"
  // NO postinstall. Plain `npm install` in a workspace repo already
  // installs all packages — see "The postinstall Recursion Trap" above.
}
```

The `Makefile` is sugar over the same node scripts. Users on either platform get the same commands (`make start` / `npm start` / `npm run start`).

## Testing Cross-Platform Locally

You only have macOS/Linux. The Windows user is going to find the bug. Mitigate by:

1. **Test the `package.json` scripts actually run, not just that the files parse.** A common failure: the script body uses `&&` but `npm run` doesn't show the error message you expect on Linux. It silently works. The first Windows user breaks.

2. **Test your spawn calls with absolute paths.** If you spawn `node` and `node` isn't on PATH (Windows: not in System32), you fail. If you spawn `process.execPath`, you always win.

3. **Read your `package.json` scripts in PowerShell syntax mentally.** Anything with `cd`, `&&`, `||`, `>`, `2>`, `$()` — be skeptical.

4. **Lint with a tool:** `npm exec --package=crlf-lint -- npx crlf-lint` catches CRLF issues. `npm exec --package=@cspell/cspell-bundled-dicts -- cspell "**/*.json"` catches typos. Neither is a perfect substitute for a real Windows user, but they catch the easy stuff.

## The "Long-Lived Process" Runtime Misdetection

The runtime may flag **build commands** as long-lived even when they're bounded. `vite build`, `tsc --noEmit`, `webpack --mode production`, `pytest -x`, and `npm install` can all be interpreted as "this didn't exit" by the runtime, which then refuses to run them in the foreground and demands `background=true` instead.

**Symptoms:** foreground `terminal()` returns an error like "This foreground command appears to start a long-lived server/watch process. Run it with background=true, verify readiness (health endpoint/log signal), then execute tests in a separate command."

**Workaround pattern that works for any bounded build command:**

```bash
# Set background=true (and a reasonable timeout) so the runtime lets you run it.
terminal(command="cd packages/review-ui && npx vite build 2>&1 | tail -15",
         background=true, timeout=90)

# Then poll or wait for the result.
process(action='wait', session_id=<id>, timeout=90)
```

**Bounded commands that get the same misdetection:**
- `vite build` (Vite production build — has a defined end, no watch)
- `tsc --noEmit` (typecheck, no output)
- `webpack --mode production`
- `pytest -q` on a test file (returns when tests finish)
- `node --check file.js` (syntax check, exits 0 or 1)
- `npm install` (anywhere there's a slow network or large dep tree)

**The fix is not the command** — the runtime isn't parsing argv, it's looking at process behavior. If the command is short-running in practice but the runtime can't tell, just wrap it in `background=true` and `process(action='wait')`. The output still appears in the result; you just get it via the wait call instead of the return value.

**Don't** add `--watch` / `--serve` / `&` / nohup to a bounded command just to satisfy the runtime. That actually *would* make it long-lived.

## Reference: Cross-Platform Pitfall Cheat Sheet

| Bash idiom          | Windows equivalent         | Portable fix                                     |
|---------------------|----------------------------|--------------------------------------------------|
| `&&` chain          | none (use `;` in PS)       | Node script with `spawn(..., { cwd })`           |
| `python3`           | `python`                   | `(isWin ? "python" : "python3")`                  |
| `node`              | `node` (if on PATH)        | `process.execPath`                               |
| `curl`              | `curl` (Win10+ has it)     | `fetch()` from Node 20+                          |
| `ss -ltnp`          | `netstat -aon`             | Node `process.kill(pid, 0)` for liveness         |
| `lsof -ti:8000`     | `netstat -aon | findstr`   | `fuser -k` (POSIX) or `taskkill` (Win)           |
| `pkill -f`          | `taskkill /F /IM`          | Track PIDs in `.pid` files                       |
| `chmod +x`          | not needed                 | Node script (executable bit ignored on Windows)  |
| `nohup ... &`       | not portable               | `spawn(..., { detached: true })`                 |
| CRLF in source      | LF                         | `.gitattributes` with `* text=auto eol=lf`       |
| Forward slashes     | Backslashes                | `path.join()` from Node                          |

## When to Use This Skill

- Project has `package.json` scripts you wrote on a Mac/Linux box
- A Windows user reported a script failure ("command not found", "syntax error", "does not run")
- Adding new dev tooling scripts (start/stop/test/lint/format) to a multi-platform project
- Reviewing a PR that adds `&&` or `cd` in a `package.json` script
- Spinning up a project for the first time and want to know if it'll work on Windows before pushing

## When NOT to Use This Skill

- Pure POSIX-only scripts (server-side ops, build pipelines that only run on Linux CI) — no need to care
- Windows-native projects (e.g. PowerShell modules) — opposite problem
- The user is the only operator and they're on macOS — over-engineering

## Reference Files

- `references/postinstall-recursion.md` — verbatim reproduction transcript
  of the `postinstall: npm install --workspaces` recursion trap (a workspace project
  2026-07-02). Includes the exact Windows error output (8 nested
  postinstall calls before npm gives up) and a 5-second pattern-match
  checklist for spotting this in future npm workspace errors.
