---
name: history-recovery
description: Full playbook for recovering past work across all Hermes history stores on the workstation — live SQLite, archived jsonl transcripts, Discord ingest, Hindsight direct API, filesystem date windows, and both GitHub identities. Use when "do you remember X" returns nothing or only a dominant-topic's noise.
tags: [memory, recovery, sqlite, hindsight, discord, session-search]
---

# History Recovery — finding past work when recall misses it

For "do you remember the X thing we did?" queries where `session_search`,
Hindsight recall, and obvious greps all miss or return a dominant topic's
noise. Complements `session-recall` (which covers reading raw session files
and never trusting summaries) — this skill adds the STORE MAP and the SWEEP
ORDER. Verified end-to-end 2026-09-30: recovered a project that existed
ONLY as a GitHub repo with zero session mentions.

## Store map (the workstation)

| Store | Path | Notes |
|---|---|---|
| Live session DB | `~/.hermes/state.db` → `/mnt/storage/hermes/state.db` | SQLite; **only recent weeks**; query read-only: `sqlite3 "file:/mnt/storage/hermes/state.db?mode=ro&immutable=1"`; tables `sessions(id,title,started_at...)`, `messages(id,session_id,role,content,timestamp)` |
| Archived transcripts | `/mnt/storage/hermes/sessions/*.jsonl` | Older eras (Apr–May 2026); grep directly; beware thousands of `session_cron_*` files flooding listings |
| Markdown exports | `~/the agent/sessions-md/*.md` | Session dumps + `db_*` cron transcripts |
| Discord ingest | `~/.hermes/discord_ingest/all_messages.json` | Flat JSON array of all Discord messages — often the FASTEST way to re-read a past conversation verbatim |
| Hindsight | `POST http://localhost:9177/v1/default/banks/hermes/memories/recall` | Daemon, NOT the broken python tools; endpoint list at `GET /openapi.json` |

## Sweep order

1. **session_search** discovery + the live DB (fast, catches recent).
2. **FTS with noise exclusion** — when one topic dominates history, query
   user messages on the term AND exclude the dominant topic:
   `WHERE role='user' AND content LIKE '%lgc%' AND content NOT LIKE '%quiz%'`.
   (Plain session_search with NOT terms often still floods with the big topic.)
3. **Hindsight recall with concrete artefact names** — generic queries
   ("LGC lookup search app") return noise; re-query using names harvested
   from any related file (catalogue titles, report filenames). Specific
   proper nouns rank far better than descriptions.
4. **Filesystem date-window scan** — once ANY related file surfaces (PDF,
   report, deliverable), sweep its mtime window:
   `find ~ -maxdepth 2 -newermt "<date>" ! -newermt "<date+3d>" -type f`.
   Sibling scripts/reports identify the project's whole working set.
5. **Both GitHub identities early** — `api.github.com/users/yourusername/repos`
   AND the the company org. Projects can exist ONLY as remote repos (no local
   clone, no session mention) — this is where the LGC search app was hiding;
   no transcript search could ever have found it.
6. **Then ask the user, with evidence in hand** — after the sweep he answered
   in one line ("it was the AXIO catalogue" + repo URL). Asking before the
   sweep wastes the question; asking after gets a precise pointer.

## Pitfalls

- Session DBs are per-machine: the workstation's live DB won't contain sessions from
  the Workstation or a VPS — check which host the work likely happened on
  before concluding "not found".
- Hindsight recall ranks its OWN ingest corpus; projects never discussed in
  chat are invisible to every transcript/Hindsight store. The GitHub repos
  API is the only complete inventory of deliverables.
- Read-only mode (`?mode=ro&immutable=1`) is mandatory on the live DB —
  the gateway holds it open and a writer connection can corrupt state.