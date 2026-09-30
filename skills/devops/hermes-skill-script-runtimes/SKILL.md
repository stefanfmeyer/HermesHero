---
name: hermes-skill-script-runtimes
description: Run Python-based Hermes skill scripts (setup.py, API wrappers like google_api.py) on the workstation, where ~/.hermes/skills is a symlink to /mnt/storage/hermes/skills, system python lacks the deps, and `python` is not on PATH. Fixes hermes_constants ModuleNotFoundError, builds uv venvs for skill deps, and catches SKILL.md-vs-script flag mismatches before quoting them to the user.
version: 1.0.0
---

# Hermes Skill Script Runtimes (the workstation)

How to execute the Python scripts bundled inside Hermes skills on this machine.
Applies to any skill whose SKILL.md instructs `python .../scripts/foo.py`
(google-workspace, and any other skill with a `scripts/` directory).

## When this applies

- A skill says to run `python <skill>/scripts/setup.py ...` and it fails with
  `ModuleNotFoundError: No module named 'hermes_constants'`
- A skill script imports third-party packages (`googleapiclient`,
  `google_auth_oauthlib`, ...) that are not installed system-wide
- `python: command not found` (only `python3` exists on this box)

## Environment facts (the workstation)

- `~/.hermes/skills` is a **symlink** → `/mnt/storage/hermes/skills` (skills
  live on the 1TB HDD)
- `hermes_constants.py` lives at `~/.hermes/hermes-agent/hermes_constants.py`
- `uv` is available at `~/.hermes/bin/uv` (plus `uvx`, `tirith`)
- No `python` alias — use `python3` or a venv's interpreter
- Google API venv for the google-workspace skill: `~/.hermes/gws-venv`
  (created via uv; contains google-api-python-client, google-auth-oauthlib,
  google-auth-httplib2)

## Pitfall 1 — hermes_constants import failure (symlinked skills dir)

Skill setup scripts do:

```python
HERMES_AGENT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERMES_AGENT_ROOT))
```

`resolve()` follows the skills symlink, so `parents[4]` lands on
`/mnt/storage/hermes` — NOT `~/.hermes/hermes-agent` where
`hermes_constants.py` actually lives. Import fails.

**Fix (durable):** copy `hermes_constants.py` into the skill's own `scripts/`
directory. The script's own directory is `sys.path[0]`, so the import succeeds
regardless of symlinks:

```bash
cp ~/.hermes/hermes-agent/hermes_constants.py \
   /mnt/storage/hermes/skills/<category>/<skill>/scripts/hermes_constants.py
```

(Done already for google-workspace on 2026-09-02.)

**Anti-pattern that does NOT work:** symlinking `hermes_constants.py` into
`~/.hermes/` — the script never looks there; only `parents[4]` of the
resolved path and the script's own dir are on its sys.path.

## Pitfall 2 — missing third-party deps

Don't pollute system python. Create a per-purpose venv with uv:

```bash
~/.hermes/bin/uv venv ~/.hermes/<name>-venv --python python3
~/.hermes/bin/uv pip install --python ~/.hermes/<name>-venv/bin/python <pkgs>
```

Then always invoke skill scripts with the venv interpreter, e.g.:

```bash
~/.hermes/gws-venv/bin/python ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --check
```

Shell state (exported PYTHONPATH etc.) does NOT persist reliably between
terminal calls — never rely on it as the fix; make the fix filesystem-level
(copied file, venv) so it survives.

## Pitfall 3 — SKILL.md documents flags the installed script lacks

Skill docs can be newer than the installed script. Example: the
google-workspace SKILL.md shows `--auth-url --services email,calendar
--format json`, but the installed `setup.py` rejects `--services` and
`--format` entirely.

**Rule:** run `<script> --help` once before quoting any flag to the user.
When a documented flag is missing, silently fall back to the plain command
(`setup.py --auth-url` defaults to all scopes) — don't make the user debug
your CLI invocation.

## Verification

1. `<venv>/bin/python <script> --check` (or equivalent) exits 0
2. Re-run the same command in a FRESH terminal call — if it fails there but
   worked before, you depended on non-persistent shell state; redo the fix
   at the filesystem level.

## Related

- `references/google-oauth-setup-notes.md` — live session detail from the
  2026-09-02 you@example.com OAuth setup: installed setup.py flag
  mismatch, the expected localhost:1 "infinite load" after consent,
  PKCE pending-session overwrite behavior, and Google Cloud console
  checklist for gmail.com accounts.
- `google-workspace` skill — the main consumer of these runtimes on this box
- Note: google-workspace is a bundled skill (protected — do not edit). Its
  SKILL.md flag mismatch and the localhost:1 redirect guidance are recorded
  here instead.