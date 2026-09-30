#!/usr/bin/env python3
"""
Hindsight Daily Ingest — YourHost edition
Reads session messages from state.db (SQLite), extracts facts via LLM,
and retains them to Hindsight via direct API.

Verified patterns from hindsight-integration skill:
- state.db (SQLite) not .jsonl files
- started_at is epoch float, not date string
- Exclude source='cron' sessions
- Single LLM call (not batched) for extraction
- Direct API with async: True for retain
- Direct ollama.com/v1 endpoint (not localhost:11434 — returns 401 for cloud models)
"""

import json
import re
import sqlite3
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

# === Config ===
DB_PATH = Path.home() / ".hermes" / "state.db"
PENDING_FACTS = Path.home() / ".hermes" / "hindsight" / "pending_facts.json"
HINDSIGHT_API = "http://localhost:9177/v1/default/banks/hermes/memories"

# LLM config — reads from hindsight config.json
HINDSIGHT_CONFIG = Path.home() / ".hermes" / "hindsight" / "config.json"
LLM_MODEL = "glm-5.3-flash:cloud"
LLM_API_BASE = "https://ollama.com/v1"
LLM_API_KEY = None  # loaded from config

# Extraction prompt
EXTRACTION_PROMPT = """You are a fact extraction engine. Extract key facts from the following conversation sessions.
For each fact, provide a concise statement (max 120 chars) that would be useful as long-term memory.

Rules:
- Extract up to 20 facts maximum
- Focus on: decisions made, preferences expressed, project details, technical findings, user corrections, important context
- Skip: greetings, small talk, tool output, system messages
- Skip facts that are trivial or will be stale within a week
- Each fact must be self-contained (readable without the conversation context)

Return ONLY a JSON array of objects with "content" and "context" fields:
[{"content": "fact text", "context": "brief context label"}, ...]

Conversation messages (truncated, newest first):"""

MSG_TRUNCATE = 800
MAX_FACTS = 20
BATCH_SIZE = 10
LLM_TIMEOUT = 120
MAX_MESSAGES = 200  # cap to avoid huge LLM calls

# Cron jobs whose FINAL OUTPUT (delivered briefing) should also be ingested.
# We ingest only the last substantive assistant message per session — not the
# prompt, not tool output — so the cron noise never pollutes the fact store.
CRON_INGEST_JOB_IDS = {"c92eb27e8ccd"}  # Daily Email & Calendar Briefing
CRON_OUTPUT_MIN_LEN = 500     # final assistant output must be at least this long
CRON_OUTPUT_TRUNCATE = 6000   # allow full briefings through (normal cap is 800)


def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_config():
    """Load LLM config from hindsight config.json."""
    global LLM_MODEL, LLM_API_BASE, LLM_API_KEY
    if HINDSIGHT_CONFIG.exists():
        with open(HINDSIGHT_CONFIG) as f:
            cfg = json.load(f)
        LLM_MODEL = cfg.get("llm_model", LLM_MODEL)
        LLM_API_BASE = cfg.get("llm_api_base", LLM_API_BASE)
        LLM_API_KEY = cfg.get("llm_api_key", LLM_API_KEY)
    if not LLM_API_KEY:
        log("WARNING: no LLM API key found in config, LLM extraction will fail")


def check_daemon_health():
    """Check if Hindsight daemon is healthy."""
    try:
        r = requests.get("http://localhost:9177/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def load_substantive_messages(date_str):
    """Load substantive messages from state.db for a given date.
    date_str format: YYYYMMDD
    """
    d = datetime.strptime(date_str, "%Y%m%d").date()
    start_epoch = datetime.combine(d, datetime.min.time()).timestamp()
    end_epoch = datetime.combine(d + timedelta(days=1), datetime.min.time()).timestamp()

    msgs = []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for content, role, session_id, source in conn.execute("""
            SELECT m.content, m.role, m.session_id, s.source
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE s.started_at >= ? AND s.started_at < ?
              AND s.source NOT IN ('cron')
              AND m.role IN ('user', 'assistant')
              AND m.content IS NOT NULL
              AND length(m.content) >= 50
            ORDER BY m.timestamp
        """, (start_epoch, end_epoch)):
            if "CONTEXT COMPACTION" in content:
                continue
            msgs.append(content[:MSG_TRUNCATE])
            if len(msgs) >= MAX_MESSAGES:
                break
    finally:
        conn.close()
    return msgs


def load_cron_outputs(date_str):
    """Load final assistant outputs from whitelisted cron jobs for a given date.
    Only the last substantive assistant message per session is returned —
    this is the delivered briefing text, not the prompt or tool noise.
    date_str format: YYYYMMDD
    """
    d = datetime.strptime(date_str, "%Y%m%d").date()
    start_epoch = datetime.combine(d, datetime.min.time()).timestamp()
    end_epoch = datetime.combine(d + timedelta(days=1), datetime.min.time()).timestamp()

    outputs = []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        session_ids = [
            row[0]
            for row in conn.execute(
                """
                SELECT s.id FROM sessions s
                WHERE s.started_at >= ? AND s.started_at < ?
                  AND s.source = 'cron'
                ORDER BY s.started_at
                """,
                (start_epoch, end_epoch),
            )
            if any(f"cron_{job_id}_" in (row[0] or "") for job_id in CRON_INGEST_JOB_IDS)
        ]

        for sid in session_ids:
            row = conn.execute(
                """
                SELECT m.content FROM messages m
                WHERE m.session_id = ?
                  AND m.role = 'assistant'
                  AND m.content IS NOT NULL
                  AND length(m.content) >= ?
                ORDER BY m.id DESC
                LIMIT 1
                """,
                (sid, CRON_OUTPUT_MIN_LEN),
            ).fetchone()
            if row and row[0]:
                outputs.append(
                    f"[Cron job final output — Daily Email & Calendar Briefing]\n{row[0][:CRON_OUTPUT_TRUNCATE]}"
                )
    finally:
        conn.close()
    return outputs


def load_pending_facts():
    """Load any pending facts from previous failed retains."""
    if not PENDING_FACTS.exists():
        return []
    try:
        with open(PENDING_FACTS) as f:
            return json.load(f)
    except Exception:
        return []


def save_pending_facts(facts):
    """Save facts that couldn't be retained for next run."""
    PENDING_FACTS.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FACTS, "w") as f:
        json.dump(facts, f, indent=2)


def extract_facts(messages):
    """Send messages to LLM and get extracted facts as JSON."""
    # Join messages into one chunk
    joined = "\n\n---\n\n".join(messages)

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": joined[:50000]},  # cap at 50K chars
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3},
    }

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    try:
        r = requests.post(
            f"{LLM_API_BASE}/chat/completions",
            json=payload,
            headers=headers,
            timeout=LLM_TIMEOUT,
        )
        if r.status_code != 200:
            log(f"LLM error {r.status_code}: {r.text[:200]}")
            return []

        data = r.json()
        content = data["choices"][0]["message"]["content"]

        # Strip code fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Try direct parse first
        try:
            facts = json.loads(content)
            if isinstance(facts, dict):
                facts = [facts]
            return facts[:MAX_FACTS]
        except json.JSONDecodeError:
            pass

        # Fallback: try to find JSON array in the response
        array_match = re.search(r'\[\s*\{[^\]]*\}\s*\]', content, re.DOTALL)
        if array_match:
            try:
                facts = json.loads(array_match.group(0))
                if isinstance(facts, dict):
                    facts = [facts]
                log(f"Fallback parse succeeded: {len(facts)} facts")
                return facts[:MAX_FACTS]
            except json.JSONDecodeError:
                pass

        # Fallback: try to find JSON object
        obj_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if obj_match:
            try:
                facts = json.loads(obj_match.group(0))
                if isinstance(facts, dict):
                    facts = [facts]
                log(f"Fallback parse (single object): {len(facts)} facts")
                return facts[:MAX_FACTS]
            except json.JSONDecodeError:
                pass

        # Last resort: try to extract facts from markdown list
        lines = content.split('\n')
        facts = []
        for line in lines:
            line = line.strip()
            if line.startswith('- **') or line.startswith('- '):
                # Extract content after the bullet
                text = re.sub(r'^- \*\*.*?\*\*:\s*', '', line)
                text = re.sub(r'^- ', '', text)
                if text and len(text) > 10:
                    facts.append({"content": text[:120], "context": "session ingest"})
        if facts:
            log(f"Fallback markdown parse: {len(facts)} facts")
            return facts[:MAX_FACTS]

        log(f"JSON parse error: could not extract facts from response")
        log(f"LLM response (first 500 chars): {content[:500] if 'content' in dir() else 'N/A'}")
        return []
    except Exception as e:
        log(f"LLM call failed: {e}")
        return []


def retain_facts(facts):
    """Retain facts to Hindsight via direct API. Returns (retained, failed_list)."""
    if not facts:
        return 0, []

    retained = 0
    failed = []

    for i in range(0, len(facts), BATCH_SIZE):
        batch = facts[i : i + BATCH_SIZE]
        items = []
        for f in batch:
            content = f.get("content", "") if isinstance(f, dict) else str(f)
            context = f.get("context", "session ingest") if isinstance(f, dict) else "session ingest"
            if content:
                items.append({"content": content, "context": context})

        if not items:
            continue

        payload = {"async": True, "items": items}
        try:
            r = requests.post(HINDSIGHT_API, json=payload, timeout=30)
            if r.status_code in (200, 201, 202):
                retained += len(items)
                log(f"  Retained batch {i//BATCH_SIZE + 1}: {len(items)} facts")
            else:
                log(f"  Retain failed (HTTP {r.status_code}): {r.text[:200]}")
                failed.extend(batch)
        except Exception as e:
            log(f"  Retain error: {e}")
            failed.extend(batch)

        time.sleep(0.3)

    return retained, failed


def main():
    log("Hindsight session ingest starting")

    # Check daemon health
    if not check_daemon_health():
        log("ERROR: Hindsight daemon not healthy on port 9177")
        print("ERROR: Hindsight daemon not healthy — run keepalive first")
        sys.exit(1)
    log("Daemon health: OK")

    # Load config
    load_config()

    # Determine date — default to today
    date_str = datetime.utcnow().strftime("%Y%m%d")
    if len(sys.argv) > 1:
        date_str = sys.argv[1]

    # Load pending facts
    pending = load_pending_facts()
    if pending:
        log(f"Loaded {len(pending)} pending facts from previous run")

    # Load today's messages
    msgs = load_substantive_messages(date_str)
    log(f"Loaded {len(msgs)} substantive messages from {date_str}")

    # Load final outputs from whitelisted cron jobs (briefings etc.)
    cron_outputs = load_cron_outputs(date_str)
    log(f"Loaded {len(cron_outputs)} whitelisted cron job outputs from {date_str}")
    msgs = msgs + cron_outputs

    if not msgs and not pending:
        log("No substantive messages or pending facts to process")
        log("Done. Total retained this run: 0")
        return

    # Extract facts via LLM
    new_facts = []
    if msgs:
        log(f"Sending {len(msgs)} messages to LLM for extraction...")
        new_facts = extract_facts(msgs)
        log(f"LLM extracted {len(new_facts)} facts")

    all_facts = pending + new_facts

    # Retain to Hindsight
    log(f"Retaining {len(all_facts)} facts to Hindsight...")
    retained, failed = retain_facts(all_facts)

    # Save any failed for next run
    if failed:
        save_pending_facts(failed)
        log(f"Saved {len(failed)} failed facts as pending for next run")
    elif PENDING_FACTS.exists():
        # Clear pending if all succeeded
        PENDING_FACTS.unlink()

    log(f"Done. Total retained this run: {retained}")
    print(f"\n=== Hindsight Daily Ingest — {date_str} ===")
    print(f"Daemon health: OK")
    print(f"Messages loaded: {len(msgs)}")
    print(f"Pending facts processed: {len(pending)}")
    print(f"LLM extracted: {len(new_facts)}")
    print(f"Retained: {retained}")
    print(f"Failed (saved as pending): {len(failed)}")


if __name__ == "__main__":
    main()