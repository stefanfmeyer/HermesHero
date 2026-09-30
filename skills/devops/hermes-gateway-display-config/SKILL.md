---
name: hermes-gateway-display-config
description: "Configure how the Hermes gateway renders tool progress, streaming, and previews per platform (Discord/Telegram/Slack). Covers the display setting resolution chain, tool_progress modes (all/new/verbose/off), the preview-truncation fallback bug, and how to make tool calls show in FULL instead of truncated previews. Use when: tool-call previews get cut off in chat, user complains commands/messages are truncated, or any 'show more/less in gateway messages' request."
tags: [hermes-agent, gateway, discord, display, configuration]
---

# Hermes Gateway Display Configuration

## Overview

The gateway renders tool-call "progress" messages (e.g. `💻 terminal` with a code block, `🐍 Running code` with a preview) before each tool executes. How much of each tool call is shown is governed by per-platform display settings in `~/.hermes/config.yaml`. The default non-verbose mode truncates these previews — the user requires FULL commands visible in Discord.

## When to Use

- User says commands/tool calls are being "cut off" in Discord/Telegram/Slack
- User asks to see full commands, full arguments, or more detail in gateway messages
- Any config request about how the gateway displays progress, streaming, or reasoning

## Setting Resolution Chain

Per-platform display settings resolve in `gateway/display_config.py::resolve_display_setting()`:

1. `display.platforms.<platform>.<key>` (most specific, wins)
2. `display.<key>` (global)
3. Built-in platform defaults (`_GLOBAL_DEFAULTS` / tier defaults in `display_config.py`)

Valid keys include: `tool_progress`, `tool_preview_length`, `tool_progress_grouping` (`accumulate`|`separate`), `show_reasoning`, `streaming`, `live_status`, `friendly_tool_labels`.

## tool_progress modes

| Mode | Behavior |
|------|----------|
| `all` | Every tool call gets a progress line; non-terminal tools show a short preview capped at `tool_preview_length` (fallback 40 chars) |
| `new` | Progress line only when the tool changes from the previous call |
| `verbose` | FULL detail: terminal commands render as complete fenced code blocks, other tools show full JSON args; `tool_preview_length: 0` correctly means unlimited here |
| `off` / `log` | No progress messages |

## The truncation pitfall (verified 2026-09)

Even with `display.tool_preview_length: 0` (= unlimited) set globally, the gateway's non-verbose path in `gateway/run.py` (~line 19788) hardcodes a fallback cap:

```python
_cap = _pl if _pl > 0 else 40
```

So `tool_preview_length: 0` gets treated as 40 chars and terminal code blocks are sliced with `...` on Discord. **`0` does NOT mean unlimited in the non-verbose path.** The fix is to switch the platform to verbose mode:

```bash
hermes config set display.platforms.discord.tool_progress verbose
```

In verbose mode the code block renders the full command (`_code_block_full`) and other tools render full JSON args with no cap.

Note: `patch`/`write_file` on `~/.hermes/config.yaml` is refused (security-sensitive) — always use `hermes config set`.

## the user's standing preference (2026-09-12)

Discord must show FULL commands and full tool-call arguments — never truncated previews. Config in place:

```yaml
display:
  platforms:
    discord:
      streaming: false
      show_reasoning: false
      tool_progress: verbose
```

Telegram is untouched (keeps default compact previews). If a future session sees truncated commands in Discord again, check this key survived config migrations, then consider fixing the `_pl if _pl > 0 else 40` fallback in `gateway/run.py` upstream.

## Changes require a restart

Display config is read at session/gateway start. After changing it, the gateway needs `/restart` (user must approve — never restart the gateway from inside a session without the user's explicit approval). CLI sessions: exit and relaunch, or `/reset` for toolset changes.

## Verification

After restart, run a terminal command in Discord and confirm the message shows the complete command inside the code block, with no `...` truncation. Also confirm verbose didn't blow up message length for very long commands — Discord's 2000-char limit applies; the gateway chunks long messages natively.