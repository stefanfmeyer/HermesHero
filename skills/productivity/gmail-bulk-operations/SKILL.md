---
name: gmail-bulk-operations
description: Bulk Gmail mailbox operations via the Hermes google_api.py wrapper - batch spam reporting, sender blocking, bulk labeling, and mass cleanup. Covers the wrapper's quirks (empty-result format, missing pagination, scope limits) and ships a reusable batch spam-reporting script.
version: 1.0.0
author: agent
license: MIT
metadata:
  hermes:
    tags: [Gmail, Google, Email, Spam, Bulk, Cleanup]
---

# Gmail Bulk Operations

Bulk mailbox actions (report-spam across many senders, block lists, bulk
labeling/cleanup) using the Hermes `google_api.py` wrapper from the
`google-workspace` skill. That skill covers single-message operations;
this one covers batch/sweep patterns and the wrapper's pitfalls.

## When to use

- User asks to "block/report spam for X, Y, Z" senders (a blocklist task)
- Bulk moving/labeling messages by sender or query
- Post-cleanup verification ("did everything actually move?")

## Setup

Reuse the google-workspace auth token (`~/.hermes/google_token.json`).
Run everything with a Python that has `googleapiclient` installed - on
the workstation that is `~/.hermes/gws-venv/bin/python`. Plain `python` is NOT on
PATH; `gws` binary is not installed - the wrapper falls back to the
Python client library, which works fine.

```bash
PY="$HOME/.hermes/gws-venv/bin/python"
GAPI="$HOME/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
$PY $GAPI gmail search "is:unread" --max 10
```

## Core operations

### Report a message as spam
Adding the `SPAM` label IS Gmail's "Report spam" action (feeds Google's
learning engine, moves message out of inbox):

```bash
$PY $GAPI gmail modify MESSAGE_ID --add-labels SPAM
```

### Identify a brand's real sender addresses
Brand names in a briefing ("block Termly") are display names. Find the
actual addresses first - senders often use multiple (marketing vs.
transactional, `info@` vs `no-reply@`):

```bash
$PY $GAPI gmail search "from:termly" --max 10
# group unique From: values before acting
```

### Batch spam reporting
Use the packaged script (handles pagination gaps, empty-result parsing,
rate limiting, and verification):

```bash
$PY $HERMES_HOME/skills/productivity/gmail-bulk-operations/scripts/gmail_spam_report.py
# edit TARGETS dict in the script for the blocklist, or pass an ad-hoc query:
$PY .../gmail_spam_report.py "from:spam.example.com"
```

## Pitfalls (all hit in real use)

1. **Empty search results are NOT JSON.** The wrapper prints
   `No messages found.` as plain text, so `json.loads` throws on empty
   results. Always check `startswith("No messages found")` before parsing.

2. **Search does not paginate.** `--max` is a single `maxResults` call,
   and the wrapper fetches metadata per message (slow: ~1s/msg at scale).
   A 100-message cap silently misses the tail of high-volume senders
   (one sender had 100+ mailings). After a bulk pass, ALWAYS re-run the
   search and report what remains, loop until clear.

3. **Timeouts at scale.** Reporting 100+ messages one-by-one through the
   wrapper exceeds a 300s terminal timeout. Run per-sender batches, keep
   output quiet (redirect modify stdout to /dev/null), and split across
   terminal calls if needed.

4. **Blocking filters need a scope the default token lacks.** The
   standard Hermes OAuth grant has gmail.readonly/send/modify but NOT
   `gmail.settings.basic`, so `users().settings().filters()` is
   unavailable - true server-side "Block sender" filters cannot be
   created via API. Options: (a) spam-report only and let Google learn,
   (b) user creates filters in Gmail UI, (c) periodic sweep script that
   auto-reports anything from the blocklist. Get explicit user choice -
   do not silently pick one.

5. **`in:inbox` verification is the ground truth.** Label state in search
   results can be stale mid-run; verify with `QUERY in:inbox` returning
   zero messages before reporting success.

6. **Spam-reporting is not unsubscribing.** It does not send
   List-Unsubscribe requests. If the user was legitimately subscribed,
   mention that unsubscribe headers are the proper removal path.

## References

- `references/blocked-senders-2026-09.md` — mapped From: addresses behind
  brand display names (Termly, Casetify, dbrand, ESPN, etc.), ready-made
  block queries, and the user's report-only decision. Update or supersede
  when the blocklist changes.

## Related

- `google-workspace` (bundled) - auth setup, single-message ops, search syntax
- `himalaya` - IMAP alternative for accounts without API access