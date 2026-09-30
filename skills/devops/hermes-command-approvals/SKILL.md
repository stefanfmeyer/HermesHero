---
name: hermes-command-approvals
description: "Configure and reason about Hermes Agent's command approval gate — approval modes (manual/smart/off), the Tirith security scanner, dangerous-command detectors, the command_allowlist, and approvals.deny rules. Use when a shell command is blocked by an approval prompt, the user asks to skip/loosen/tighten command approvals, curl|python3-style commands keep getting flagged as 'pipe to interpreter', or questions arise about what YOLO mode still protects."
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Hermes Command Approvals

## When to load

- A terminal command returns `status: pending_approval` / "⚠️ Command Approval Required"
- User asks "how do I stop these approval prompts", "always allow these commands", "make Hermes stop asking"
- Tirith flags something like `[HIGH] Pipe to interpreter: curl | python3` or `[MEDIUM] Schemeless URL in sink context`
- User wants to tighten security instead (deny rules)
- Question about what `--yolo` / `approvals.mode: off` actually disables

## How the gate works

Three independent layers decide whether a command runs without asking (verified
in `tools/approval.py`):

1. **Tirith security scanner** (`security.tirith_enabled`, default on) — pattern
   findings like pipe-to-interpreter and schemeless URLs. Both `block` and
   `warn` verdicts go through the normal approval flow (approvable, not hard blocks).
2. **Dangerous-command detectors** — built-in patterns: recursive delete,
   `git reset --hard`, force push, gateway stop/restart, heredoc script
   execution, overwrite of `~/.hermes/config.yaml` or `.env` via
   sed/tee/`>`/cp, SQL DELETE without WHERE, sudo with askpass, etc.
3. **Hardline patterns** — NEVER bypassable, even in YOLO mode: hermes/gateway
   self-kill, heredoc script execution, root-path deletes, and friends.

## Approval modes

`approvals.mode` in `~/.hermes/config.yaml` (per-profile):

- `manual` (default) — prompt on any warning
- `smart` — an auxiliary LLM risk-assesses each flagged command; auto-approves
  low-risk (e.g. `curl localhost ... | python3 -c 'parse json'`), escalates
  high-risk to the user. Smart-DENY hard-blocks non-owner sessions; an
  interactive owner can override for one operation.
- `off` — skip all approval prompts (YOLO). Hardline patterns and
  `approvals.deny` globs still enforce.

```bash
hermes config set approvals.mode smart   # middle ground
hermes config set approvals.mode off     # full YOLO
```

## What YOLO does NOT disable

- Hardline never-bypassable patterns
- `approvals.deny` fnmatch globs — deny matches fire BEFORE the yolo bypass
- Secret redaction (`security.redact_secrets`) — independent of approvals

## Config changes take effect mid-session

The approval gate reads config.yaml through an mtime-keyed config cache.
`hermes config set approvals.mode off` applies to the very next command — no
gateway restart needed. (Exception: the `HERMES_YOLO_MODE` env var is frozen
at process import; config-file values are not.)

## Pitfalls

- **"Always" on a Tirith finding is session-scoped by design** — it re-prompts
  every new session. There is deliberately no permanent allowlist for Tirith
  findings (too easy to blanket-suppress a whole scanner rule category).
- **Compound commands can never be permanently allowlisted.**
  `_command_matches_permanent_allowlist` returns False for any command
  containing `\n`, `&&`, `||`, `;`, `&`, `|`, `<`, `>`, a backtick, or `$(` —
  so `command_allowlist` only ever matches simple commands and globs like
  `podman *`. Don't try to allowlist a piped command; it cannot work.
- **Tirith flags `curl | python3` as HIGH pipe-to-interpreter** even for
  localhost APIs. If the user wants to keep manual mode, adapt the command
  instead: write curl output to a temp file and parse it separately, or use
  `execute_code` with urllib/requests rather than a shell pipe.
- **Don't edit config.yaml in-place from a tool call** to change approvals —
  the config path is itself a gated sensitive path (the gate reads it live, so
  the pair is deliberate). Always use `hermes config set`.

## Verification

After changing the mode, re-run the exact command that was previously blocked
and confirm it executes without a pending-approval result. Never report the
change as done from the config write alone.

## the user's environment (set 2026-09-04)

the user chose `approvals.mode: off` (full YOLO) after repeated Tirith prompts on
`curl localhost:9177 ... | python3` calls against the Hindsight API. Do not
propose re-enabling approval prompts unless he asks. Hardline patterns, any
future `approvals.deny` rules, and secret redaction still protect.

## References

- `references/approval-internals.md` — source-level details from
  `tools/approval.py`: persistence semantics, smart-approval flow, deny rule
  precedence, permanent allowlist mechanics.