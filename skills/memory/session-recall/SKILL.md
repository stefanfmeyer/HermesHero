---
name: session-recall
description: How to reliably answer "what did we work on", "what happened", "remember when" — read raw session files directly, never trust embeddings or summaries.
triggers:
  - "what did we work on"
  - "what happened"
  - "remember when"
  - "what about"
  - "have we discussed"
  - "who said"
  - "what did I ask"
---

# Session Recall — Ground Truth Only

## THE PROBLEM

`session_search()` uses LLM summarization — it CAN HALLUCINATE. Semantic embeddings may contain made-up summaries. Neither is reliable for factual "what happened" queries.

## THE RULE

**For any "what did we work on / what happened / what did I say" query:**

1. **FIRST** → Read raw `~/.hermes/sessions/YYYY-MM-DD*.jsonl` files directly
2. **THEN** → Use `session_search()` only for conceptual search across many sessions
3. **NEVER** trust memory/embeddings for factual session content

## HOW TO READ SESSIONS

```python
import json
from pathlib import Path

# Get sessions from a specific date
session_files = sorted(
    Path("/Users/openstef/.hermes/sessions").glob("20260422_*.jsonl"),
    key=lambda p: p.stat().st_mtime
)

for f in session_files:
    with open(f) as fp:
        messages = [json.loads(l) for l in fp if l.strip()]
    
    # Get user messages
    user_msgs = [
        m.get("content", "")[:300]
        for m in messages
        if m.get("role") == "user" and len(m.get("content", "")) > 5
    ]
    
    if user_msgs:
        print(f"\n=== {f.name} ({len(user_msgs)} user msgs) ===")
        for msg in user_msgs:
            print(f"  • {msg[:200]}")
```

## WHY THIS MATTERS

Today (2026-04-22) I told the user we "set up semantic search and fixed recall" — complete fabrication. The truth was in the session files: the user had ripped out semantic search and was testing OpenViking. I hallucinated because I trusted embeddings over raw transcripts.

**Second case (2026-07-02, a project repo):** a session ended with a bookend claiming "Pushed 3 commits: 8f3a2b4, 1a7c4f9, 0e9d3c1" — but `git reflog` on the actual repo `/tmp/myproject` showed no such commits. The `local` HEAD was still on `404e4e9` from earlier in the day; the "3 commits" only existed in the bookend text, not on disk or remote. The session had only uncommitted changes sitting in a build directory `/tmp/myproject-build/`. The next session had to do a state diff before it could safely do anything.

**Pattern:** the bookend is generated at the end of a turn from memory of intent, not from a fresh `git log` check. Always re-verify repo state at end of turn before claiming success. When a future session asks "what did we do yesterday", trust the git log of the actual repo, not the previous session's bookend.

## WHEN TO USE SESSION_SEARCH (OK)

- Broad conceptual search across many sessions
- When you need LLM summarization to synthesize patterns across sessions
- After reading raw files to fill in context

## WHEN TO USE RAW FILES (ALWAYS FIRST)

- User asks "what did we work on today"
- User asks "what happened in the session about X"
- Any factual question about what was said or done
- User corrects you — always go to raw files immediately
