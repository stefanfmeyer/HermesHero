# Hermes Approval Gate — Source Internals

Findings read directly from `tools/approval.py` in `~/.hermes/hermes-agent`
(verified 2026-09-04). Page/line numbers drift; search by symbol names.

## Decision flow (per terminal command)

1. **Hardline patterns** fire first — NEVER bypassable, even in YOLO. Includes
   hermes/gateway self-kill (`pgrep`-expansion self-termination), heredoc
   script execution, deletes in root paths. Result is a hard block.
2. **`approvals.deny` user globs** (`approvals.deny` in config.yaml, fnmatch
   patterns) fire BEFORE the yolo/mode=off bypass. A deny match produces
   `user_deny: True` and cannot be retried or rephrased.
3. **YOLO bypass check** — `_YOLO_MODE_FROZEN or is_current_session_yolo_enabled()
   or approval_mode == "off"` skips the approval flow for everything else.
   `_YOLO_MODE_FROZEN` = `HERMES_YOLO_MODE` env var read once at module import;
   config-file `approvals.mode` is read through an mtime-keyed config cache, so
   `hermes config set approvals.mode off` takes effect mid-session.
4. **Phase 1 findings**: Tirith scan (`check_command_security`) plus
   `detect_dangerous_command`. Both `block` and `warn` Tirith verdicts become
   approvable warnings (hard-block behavior was removed; users can inspect
   and approve).
5. **Phase 2.5 smart approval** — when `approvals.mode == smart`, an auxiliary
   LLM assesses the combined warning description. Verdicts:
   - `approve` → auto-approved for THIS command only (no pattern persistence —
     deliberate, so one benign command can't blanket-suppress a detector
     category)
   - `deny` + non-owner session → hard block (`smart_denied: True`)
   - `deny` + owner (CLI/gateway/ask surface) → one-operation override allowed
6. **Phase 3 approval** — interactive prompt or gateway pending-approval round
   trip.

## Persistence semantics of approve choices

Choices: `once`, `session`, `always`, `deny`.

- Tirith warnings (`is_tirith=True`): **session-scoped only**, even when the
  user picks "always". See the persistence loop:
  `if choice == "session" or (choice == "always" and is_tirith): approve_session(...)`
  — "always" + tirith falls into the session-only branch. No
  `approve_permanent` call. This is deliberate: no permanent allowlisting of
  scanner rule categories.
- Dangerous-pattern warnings: "always" also calls `approve_permanent(key)` +
  `save_permanent_allowlist(...)` → written to `command_allowlist` in
  config.yaml.
- Smart-DENY owner overrides are always one-operation (persistence skipped
  even if an older client returns "session"/"always").

## Permanent allowlist (`command_allowlist`)

- `_command_matches_permanent_allowlist` matches exact command text or fnmatch
  globs (patterns containing `*?[`).
- **Compound commands never match**: `_has_allowlist_shell_operator` returns
  True if the command contains `\n`, `&&`, `||`, `;`, `&`, `|`, `<`, `>`,
  backtick, or `$(` — in which case the function returns False immediately.
  Piped commands therefore CANNOT be permanently allowlisted, ever.
- `load_permanent_allowlist()` bulk-loads config entries at startup;
  historical entries include dangerous-pattern keys (e.g. `recursive delete`).

## Config keys

```yaml
approvals:
  mode: manual|smart|off
  timeout: 60
  cron_mode: deny            # cron sessions can't interactive-approve
  mcp_reload_confirm: true
  destructive_slash_confirm: true
security:
  tirith_enabled: true        # master switch for the scanner
  tirith_fail_open: true      # if tirith can't be imported: allow (true) or
                              # synthesize a warn finding (false)
  allow_private_urls: false
  redact_secrets: true        # independent of approvals
```

- `security.tirith_enabled: false` disables ONLY the scanner layer; built-in
  dangerous-command detectors keep prompting.
- `security.tirith_fail_open: false` makes a missing/broken tirith import
  fail closed with a synthesized warn finding.

## Sensitive-path pairing (why in-place config edits are gated)

`~/.hermes/config.yaml` and `~/.hermes/.env` are gated sensitive paths for
terminal commands (sed -i, tee, `>`, cp) AND for file tools (write_file/patch).
This is deliberate pairing: the config file IS the security policy and the
gate reads it live (mtime-keyed cache), so a write takes effect immediately —
an agent must not be able to flip `approvals.mode` on itself via a raw file
write. Use `hermes config set` (CLI path, prompts appropriately) instead.

## Env facts seen in the wild

- Tirith rule that fires most for local API work: `[HIGH] Pipe to interpreter:
  curl | python3`, plus `[MEDIUM] Schemeless URL in sink context` for
  `curl localhost:9177/...`. Both are routine against the Hindsight API
  (localhost:9177) and are safe to approve for session.
- Workarounds when the user wants to keep manual mode: write curl output to a
  temp file and parse it in a second command, or use `execute_code` with
  urllib/requests instead of a shell pipe.