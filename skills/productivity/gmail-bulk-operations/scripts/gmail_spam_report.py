#!/usr/bin/env python3
"""Batch spam-reporting for Gmail senders via the google_api.py wrapper.

Reports all inbox messages matching each sender query as spam (adds the
SPAM label, which is Gmail's 'Report spam' action), then verifies nothing
is left in the inbox. Run with a Python that can reach google_api.py's
dependencies (e.g. ~/.hermes/gws-venv/bin/python).

Usage:
  python gmail_spam_report.py "from:spam.example.com"   # ad-hoc query
  python gmail_spam_report.py                            # uses TARGETS below

Edit TARGETS to persist a blocklist, or import process()/verify() from
another script.

Pitfalls handled here (see SKILL.md):
  - Wrapper prints 'No messages found.' plain text for empty results.
  - Wrapper search does not paginate; run repeatedly until clear.
  - Rate-limit sleep between modify calls.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes"
GAPI = HERMES_HOME / "skills/productivity/google-workspace/scripts/google_api.py"

# Persistent blocklist: "display name": "Gmail search query"
TARGETS = {
    # "Termly": "from:termlyservices@email.termly.io",
}


def _search(query, max_results=500):
    out = subprocess.run(
        [sys.executable, str(GAPI), "gmail", "search", query, "--max", str(max_results)],
        capture_output=True, text=True,
    )
    text = out.stdout.strip()
    if not text or text.startswith("No messages found"):
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"SEARCH ERROR for {query!r}: {text[:200]}", file=sys.stderr)
        return []


def _report_spam(message_id):
    out = subprocess.run(
        [sys.executable, str(GAPI), "gmail", "modify", message_id, "--add-labels", "SPAM"],
        capture_output=True, text=True,
    )
    return out.returncode == 0


def process(query, name=""):
    """Report all non-spam messages matching query. Returns count reported."""
    msgs = _search(query)
    todo = [m["id"] for m in msgs if "SPAM" not in m.get("labels", [])]
    label = f"[{name}] " if name else ""
    print(f"{label}{query}: found {len(msgs)}, to report {len(todo)}")
    fails = 0
    for mid in todo:
        if not _report_spam(mid):
            fails += 1
        time.sleep(0.05)
    if fails:
        print(f"{label}{fails} FAILED")
    return len(todo) - fails


def verify(query, name=""):
    """True if no matching messages remain in the inbox."""
    remaining = _search(query + " in:inbox")
    label = f"[{name}] " if name else ""
    if remaining:
        print(f"{label}WARNING: {len(remaining)} still in inbox")
        return False
    print(f"{label}inbox clear")
    return True


def main():
    queries = dict(TARGETS)
    if len(sys.argv) > 1:
        queries["ad-hoc"] = " ".join(sys.argv[1:])
    if not queries:
        print("No targets. Pass a query or edit TARGETS in this script.")
        return 1
    total = 0
    # Loop until clear: search is not paginated, so high-volume senders
    # may need multiple passes.
    for name, q in queries.items():
        for _ in range(3):  # bounded retries
            n = process(q, name)
            total += n
            if n == 0:
                break
    print(f"=== reported {total} message(s) as spam ===")
    print("=== verify ===")
    ok = all(verify(q, n) for n, q in queries.items())
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())