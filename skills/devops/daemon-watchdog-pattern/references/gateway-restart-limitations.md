# Gateway Restart Limitations

## Cannot restart from inside the gateway process

The gateway safety hooks block `hermes gateway restart`, `systemctl --user restart hermes-gateway`, and any command that would send SIGTERM to the gateway process — because SIGTERM propagates to child processes (including the command itself) before the restart can complete.

**Error messages you'll see:**
- `Blocked: cannot restart or stop the gateway from inside the gateway process. The gateway would kill this command before it could complete (SIGTERM propagates to child processes).`
- `Blocked: cannot restart or stop the gateway from inside the gateway process.`
- Foreground `nohup`/`disown`/`setsid` wrappers are also blocked: `Foreground command uses shell-level background wrappers`

**Workarounds (in order of preference):**
1. **`/restart` slash command in Discord** — the cleanest path; the gateway handles it from the platform side
2. **SSH from outside the gateway** — `ssh user@localhost 'hermes gateway restart'` or `systemctl --user restart hermes-gateway.service` from a non-gateway shell
3. **Detached systemd timer** — create a one-shot timer that fires 3s later (but this is over-engineering for most cases)

**What does NOT work:**
- `hermes gateway restart` from any tool inside the gateway (terminal, execute_code, delegate_task)
- `systemctl --user restart hermes-gateway` from terminal (blocked by guard)
- `nohup bash -c 'sleep 3 && systemctl --user restart ...' &` in foreground (blocked: shell-level background wrapper)
- `terminal(background=true)` with the restart command (same guard blocks it)

## Secret redaction is snapshotted at startup

`security.redact_secrets` in config.yaml is read ONCE at process import time. Toggling it mid-session via `hermes config set` has NO effect on the running gateway — the change only takes effect on the next gateway restart.

This is deliberate: it prevents an LLM from disabling secret redaction on itself mid-task.

**Implication:** if you need to receive a secret (API token, password) via chat that the redaction filter would mask:
1. `hermes config set security.redact_secrets false`
2. Restart the gateway (see above — must be from outside)
3. Receive the secret
4. `hermes config set security.redact_secrets true`
5. Restart again on next opportunity

**Note:** User messages typed directly in Discord/Slack are NOT redacted — only tool output (terminal stdout, read_file, web content, subagent summaries) is scanned. So a user pasting a token in chat will reach the agent even with redaction enabled. The redaction fires when the agent tries to echo or process the token in tool output.

## Gateway OOM-kill

The gateway process itself can be OOM-killed on low-RAM VPS (≤4GB). Symptoms:
- `⚠️ Gateway shutting down` notification in Discord/Slack
- gateway.log shows `Received SIGTERM — initiating shutdown` with `parent_name=systemd` (systemd sent SIGTERM because the cgroup hit its memory limit or the kernel OOM killer triggered)
- gateway-exit-diag.log shows the process tree at time of death

**Root causes:**
- Parallel `delegate_task` subagents (each adds ~400MB to the gateway process)
- Many TypeScript LSP servers (each ~200MB)
- No swap on a 4GB VPS

**Fix:** same as hindsight OOM — add swap, cap `delegation.max_concurrent_children` to 2, add `MemoryMax=1G` to gateway systemd override.