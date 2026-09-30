# Postinstall Recursion — npm workspaces 2026-07-02

A real reproduction transcript from the day this trap bit a Windows user. The
exact error output is below — it pattern-matches so cleanly that you should be
able to spot it on first read of any future npm workspace error.

## The mistake

I added a `postinstall` hook to a workspace `package.json`:

```jsonc
"scripts": {
  "postinstall": "npm install --workspaces --include-workspace-root",
  ...
}
```

Reasoning at the time: "I want a single `npm install` to install all workspace
packages." This was redundant — `npm install` in a workspace repo **already**
installs all workspace deps into the root `node_modules` — but the redundancy
wasn't visible until a Windows user tried it.

## The error (verbatim, Windows 11, PowerShell, Node 22, npm 10)

```
PS C:\Users\youruser\Documents\my-project> npm install

> myproject@0.1.0 postinstall
> npm install --workspaces --include-workspace-root

> myproject@0.1.0 postinstall
> npm install --workspaces --include-workspace-root

> myproject@0.1.0 postinstall
> npm install --workspaces --include-workspace-root

> myproject@0.1.0 postinstall
> npm install --workspaces --include-workspace-root

npm error A complete log of this run can be found in: C:\Users\youruser\AppData\Local\npm-cache\_logs\2026-07-02T13_33_00_037Z-debug-0.log
npm error code 1
npm error path C:\Users\youruser\Documents\my-project
npm error command failed
npm error command C:\Windows\system32\cmd.exe /d /s /c npm install --workspaces --include-workspace-root
```

## How to recognize this trap in 5 seconds

Three signals, all of which appeared in the transcript above:

1. **The same `> myproject@0.1.0 postinstall` block appears multiple times in a
   row** in the install output. (A normal postinstall runs once.)
2. **The error references the same package.json path that the user just ran
   `npm install` in** — `path C:\Users\youruser\Documents\my-project`. The
   install is recursively re-running itself in the same dir.
3. **npm delegates to `cmd.exe`** on Windows to run the postinstall:
   `command C:\Windows\system32\cmd.exe /d /s /c npm install --workspaces...`
   Each nested call shells out to cmd, runs npm install, which fires
   postinstall again, which shells out to cmd again, etc.

## The fix

One-line removal from `package.json`:

```diff
  "scripts": {
-   "postinstall": "npm install --workspaces --include-workspace-root",
    "install:all": "npm install --workspaces --include-workspace-root",
    ...
  }
```

Plain `npm install` in a workspace repo already does what the postinstall was
trying to do. Verify by:

```bash
cd <repo> && rm -rf node_modules package-lock.json
npm install 2>&1 | grep -c "npm install --workspaces"
# Should print "0" or "1" — anything higher means recursion
```

After the fix, also commit the root `package-lock.json` that npm generates —
it's the lockfile covering the full dep graph including all workspace
packages, and it makes installs reproducible across machines.

## Why I wrote the postinstall in the first place (rationale trap)

The mental model was: "I want `npm install` to feel like one command, like
`pip install -r requirements.txt` or `cargo build`." That's a fine instinct,
but npm workspaces already provide this — the root `package.json` with
`"workspaces": ["packages/*"]` **is** the equivalent of a Cargo workspace or
a Python monorepo tool. Adding a postinstall to "force" it is cargo-culting
behavior that npm already does for free.

Rule of thumb: if you find yourself writing a `postinstall` that runs
`npm install` (or any package manager install command) in a workspace repo,
stop. The workspace config is already doing that work.

## Test your fix

```bash
# Pre-fix
rm -rf node_modules packages/*/node_modules package-lock.json
npm install 2>&1 | tee /tmp/install.log
grep -c "postinstall" /tmp/install.log   # > 0 = recursion
grep -c "myproject@0.1.0 postinstall" /tmp/install.log   # > 1 = recursion

# Post-fix (no postinstall in package.json)
rm -rf node_modules packages/*/node_modules package-lock.json
npm install 2>&1 | tee /tmp/install.log
grep -c "postinstall" /tmp/install.log   # 0 expected
```

If `grep -c "postinstall"` returns anything other than 0 after the fix, you
still have a postinstall somewhere — check child package.json files too.
