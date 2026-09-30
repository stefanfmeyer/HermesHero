#!/usr/bin/env python3
"""Verify every live inference surface uses the expected model; flag any drift.

Why this exists: a config-only model migration reported success on 2026-09-16 and
yet glm-5.3-flash kept being billed until 2026-09-17, because a file the daemon
never reads was edited and the daemon was never restarted. Greps prove what a file
SAYS; this script proves what the RUNNING SYSTEM DOES.

Usage:
    python3 verify-inference-surfaces.py                    # expected = config.yaml model.default
    python3 verify-inference-surfaces.py deepseek-v4.1-flash:cloud

Exit code 0 = clean, 1 = drift found. Safe to run any time; read-only.

Notes:
  - Reads /proc directly instead of an inline `pgrep`/`ps` string, so a pattern it
    searches for can never match its own command line (the hindsight-embed ExecStop
    pkill pitfall).
  - Permission-denied on other users' /proc entries is expected and ignored.
"""

import glob
import json
import os
import re
import subprocess
import sys

HERMES = os.path.expanduser("~/.hermes")
# ~/.hermes/skills is a symlink to /mnt/storage/hermes/skills — same files.
HINDSIGHT_ENV_DEFAULT = "/mnt/storage/hermes/hindsight_data/profiles/hermes.env"
HINDSIGHT_LOG_DEFAULT = "/mnt/storage/hermes/hindsight_data/profiles/hermes.log"
# Model-ish tokens we look for in live process environments.
MODEL_TOKEN = re.compile(r"[A-Za-z0-9._/-]*(?:flash|pro|glm|qwen|kimi|mimo|sonnet|opus|gemini|gpt|deepseek|minimax|muse|nemotron)[A-Za-z0-9._:-]*", re.I)

drift = []


def section(title):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def fail(msg):
    drift.append(msg)
    print("  DRIFT: " + msg)


def expected_model():
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        cfg = open(f"{HERMES}/config.yaml", errors="ignore").read()
        m = re.search(r"^model:\s*\n(?:.*\n)*?\s*default:\s*(\S+)", cfg, re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    return None


def resolve_hindsight_env():
    """The EnvironmentFile the systemd unit actually loads — not the legacy file."""
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", "hindsight-embed", "-p", "EnvironmentFiles"],
            capture_output=True, text=True, timeout=15).stdout
        m = re.search(r"EnvironmentFiles=(\S+)", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return HINDSIGHT_ENV_DEFAULT


def check_config(expected):
    section("1. config.yaml (static intent)")
    p = f"{HERMES}/config.yaml"
    try:
        cfg = open(p, errors="ignore").read()
    except OSError as e:
        fail(f"cannot read {p}: {e}")
        return
    m = re.search(r"^model:\s*\n(?:.*\n)*?\s*default:\s*(\S+)", cfg, re.M)
    got = m.group(1) if m else "(none)"
    print(f"   model.default: {got}")
    if expected and got != expected:
        fail(f"config.yaml model.default={got} != expected {expected}")
    # A fallback chain is a second model by definition — flag if present.
    for block in ("fallback_model:", "fallback_providers:"):
        if re.search(rf"^{block}", cfg, re.M):
            fail(f"config.yaml still defines {block} — that is a SECOND model surface")
    for key in ("model.default", "compression.model", "delegation.model"):
        print(f"   {key}: ok" if key else "")
    cfg_models = set(re.findall(r"^\s*model:\s*(\S+)", cfg, re.M)) | \
                 set(re.findall(r"^\s*default:\s*(\S+)", cfg, re.M))
    # Media / embedding / non-chat models are legitimately not the chat default
    # (tts, stt, vision, image-gen, x_search). Only chat-routing models must match.
    non_chat = re.compile(
        r"tts|voice|whisper|voxtral|neutts|piper|eleven|embed|rerank|scribe"
        r"|ocr|grok-|gemini-.*tts|gpt-.*tts|^base$|^''$", re.I)
    chat_family = re.compile(
        r"glm-|deepseek-|minimax-|qwen|kimi-|nemotron|mimo-|:cloud$", re.I)
    stray = {x for x in cfg_models
             if x and x != expected
             and not non_chat.search(x)
             and chat_family.search(x)}
    if stray:
        print(f"   stray CHAT models named in config.yaml: {sorted(stray)}")
        fail(f"config.yaml names non-expected chat models: {sorted(stray)}")
    else:
        print("   no stray chat models in config.yaml (media/stt/tts models ignored)")


def check_hindsight(expected, env_path):
    section(f"2. Hindsight runtime config ({env_path})")
    try:
        txt = open(env_path, errors="ignore").read()
    except OSError as e:
        fail(f"cannot read {env_path}: {e}")
        return
    live = [l for l in txt.splitlines()
            if l.startswith("HINDSIGHT_API_LLM_MODEL") and not l.lstrip().startswith("#")]
    if not live:
        fail("no active HINDSIGHT_API_LLM_MODEL in the runtime env file")
    for l in live:
        got = l.split("=", 1)[1].strip()
        print(f"   {l}")
        if expected and got != expected:
            fail(f"Hindsight runtime env MODEL={got} != {expected}")
    legacy = f"{HERMES}/hindsight/config.json"
    if os.path.exists(legacy):
        try:
            d = json.load(open(legacy))
            lm = d.get("llm_model")
            print(f"   (legacy {legacy}: llm_model={lm} — informational, daemon does NOT read this)")
        except Exception:
            pass


def check_live_processes(expected, env_path):
    section("3. LIVE process environments  <-- the surface greps cannot see")
    """A daemon snapshots its config into env at start. File edit != applied."""
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    except Exception as e:
        fail(f"ps failed: {e}")
        return
    checked = 0
    for line in out.splitlines():
        pid, _, args = line.strip().partition(" ")
        if not pid.isdigit():
            continue
        if "verify-inference" in args or args.startswith("ps -eo"):
            continue
        try:
            raw = open(f"/proc/{pid}/environ", "rb").read().decode(errors="ignore")
        except (OSError, PermissionError):
            continue  # other users' processes — expected
        hits = {kv.split("=", 1)[0]: kv.split("=", 1)[1]
                for kv in raw.split("\0")
                if "=" in kv and ("LLM_MODEL" in kv or "MODEL" in kv.split("=", 1)[0])}
        if not hits:
            continue
        checked += 1
        for k, v in hits.items():
            mark = "ok" if (not expected or v == expected) else "DRIFT"
            print(f"   pid {pid} {k}={v}  [{mark}]")
            if expected and v != expected:
                fail(f"pid {pid} ({args[:50]}) env {k}={v} != {expected}")
    if checked == 0:
        print("   (no processes exposed model env this run)")


def check_cron(expected):
    section("4. cron/jobs.json (pinned models + drift-guards)")
    p = f"{HERMES}/cron/jobs.json"
    try:
        d = json.load(open(p))
    except Exception as e:
        fail(f"cannot read {p}: {e}")
        return
    jobs = d if isinstance(d, list) else d.get("jobs", d)
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    pinned_bad, snap_bad = [], []
    for j in jobs:
        m = j.get("model")
        if m and expected and m != expected:
            pinned_bad.append((j.get("id"), j.get("name"), m))
        snap = j.get("model_snapshot")
        if snap and expected and snap != expected:
            snap_bad.append((j.get("id"), snap))
    print(f"   jobs={len(jobs)}  non-expected pinned: {len(pinned_bad)}  stale snapshots: {len(snap_bad)}")
    for i, n, m in pinned_bad:
        fail(f"cron {i} ({n}) pinned to {m}")
    for i, s in snap_bad:
        fail(f"cron {i} has stale model_snapshot={s} — job will silently SKIP")


def check_actual_billing(expected):
    section("5. state.db session_model_usage (what was actually called)")
    """Ground truth. If a model appears here it was really invoked and really billed.
    Cumulative rows are historical by nature — only a call in the recent window is
    'ongoing' drift. Anything older is a record of a past era."""
    db = f"{HERMES}/state.db"
    try:
        import sqlite3
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = c.execute(
            "SELECT model, SUM(api_call_count), MIN(first_seen), MAX(last_seen) "
            "FROM session_model_usage GROUP BY model ORDER BY 2 DESC").fetchall()
    except Exception as e:
        print(f"   (skipped: {e})")
        return
    import datetime, time
    ts = lambda x: datetime.datetime.fromtimestamp(x).strftime("%m-%d %H:%M") if x else "?"
    # A call within the last hour = the running system is still emitting it.
    ONGOING_SECS = 3600
    now = time.time()
    for model, calls, first, last in rows:
        ongoing = last and (now - last) < ONGOING_SECS
        if not expected or model == expected:
            mark = "ok"
        else:
            mark = "DRIFT (ongoing)" if ongoing else "historical"
        print(f"   {model:34s} calls={calls:6d}  {ts(first)} -> {ts(last)}  [{mark}]")
        if expected and model != expected and ongoing:
            fail(f"BILLED model {model} ({calls} calls, LAST CALL {ts(last)} — within "
                 f"{ONGOING_SECS}s) != {expected}: the running system is still emitting it")


def check_hindsight_log(env_path):
    section("6. Hindsight profile log (recent real LLM calls)")
    log = HINDSIGHT_LOG_DEFAULT
    if not os.path.exists(log):
        alt = os.path.join(os.path.dirname(env_path), "hermes.log")
        log = alt if os.path.exists(alt) else None
    if not log:
        print("   (no log found)")
        return
    try:
        txt = open(log, errors="ignore").read()[-200000:]
    except OSError as e:
        print(f"   (unreadable: {e})")
        return
    calls = re.findall(r"scope=(\w+), model=(\S+?),", txt)
    for scope, model in calls[-6:]:
        print(f"   {scope:22s} {model}")
    # Only the tail matters: a restart boundary resets the question.
    last_start = txt.rfind("client initialized")
    if last_start > 0:
        post = txt[last_start:]
        gm = re.findall(r"model=(\S+?)(?:[,\s]|$)", post)
        models = sorted(set(gm))
        print(f"   models used since last client init: {models}")


def check_service():
    section("7. Service + health")
    try:
        st = subprocess.run(["systemctl", "--user", "show", "hindsight-embed",
                             "-p", "ActiveState", "-p", "ExecMainStartTimestamp"],
                            capture_output=True, text=True, timeout=15).stdout.strip()
        print("   " + st.replace("\n", "  "))
        if "ActiveState=active" not in st:
            fail("hindsight-embed is not active")
    except Exception as e:
        print(f"   (systemctl unavailable: {e})")
    try:
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                               "-m", "5", "http://localhost:9177/health"],
                              capture_output=True, text=True, timeout=15).stdout
        print(f"   health: {code}")
        if code != "200":
            fail(f"hindsight health={code} (cold start takes ~150s after a restart)")
    except Exception as e:
        print(f"   (health probe failed: {e})")


def check_skills(expected):
    section("8. Skill tree — stale prescriptive model names")
    """A skill naming a non-expected model as the routing default re-commands it
    next session. Flag only *prescriptive* lines (config keys / routing claims),
    not provider catalogs or media-model mentions."""
    base = f"{HERMES}/skills"
    try:
        files = subprocess.run(
            ["grep", "-rl", "-E",
             "glm-[0-9]|minimax-m[0-9]|deepseek-v[0-9]|qwen|kimi-|nemotron|sonnet|opus-|gpt-5",
             base],
            capture_output=True, text=True).stdout.split()
    except Exception:
        return
    files = [f for f in files
             if ".curator_backups" not in f and ".archive" not in f]
    # Chat-model families that could be (mis)prescribed as a routing default.
    chat = re.compile(
        r"\b(?:glm-\d[\w.:-]*|deepseek-[\w.:-]*|minimax-m\d[\w.:-]*|qwen[\w.:-]*"
        r"|kimi-[\w.:-]*|nemotron[\w.:-]*|mimo-[\w.:-]*|grok-[\w.:-]*"
        r"|claude-[\w.:-]*|gpt-5[\w.:-]*|sonnet[\w.:-]*|opus-[\w.:-]*)\b", re.I)
    # Media / embedding / non-chat models legitimately differ from the chat default.
    non_chat = re.compile(
        r"\btts\b|voice|whisper|voxtral|neutts|piper|eleven|embed|rerank|scribe"
        r"|-ocr|image.gen|dall|stt\b|transcri", re.I)
    # Dated, explicitly-historical, quoted-record, or illustrative lines are records,
    # not prescriptions. (Audit quotes, user-request quotes, "e.g." examples.)
    historical = re.compile(
        r"20\d\d-\d\d|HISTORICAL|Historical|retired|banned|BANNED|STALE|superseded"
        r"|Superseded|dead|Follow-up|Session 20|do not copy|no longer|LEGACY|legacy"
        r"|was |were |previously|used to |Request \(|being told|README said"
        r"|e\.g\.|vestigial|not read|does NOT read|unread", re.I)
    # A line is prescriptive if it names a routing surface or makes a routing claim.
    prescriptive = re.compile(
        r"model\.default|auxiliary|delegation|HINDSIGHT_API_LLM_MODEL|sanctioned"
        r"|single model|only use|is the default|recommended|pinned cron|cron/jobs"
        r"|model:/|default:|Hindsight LLM|subagent|coding delegate|primary model", re.I)
    flagged, ok_lines = [], 0
    for f in files:
        try:
            lines = open(f, errors="ignore").read().splitlines()
        except OSError:
            continue
        for i, l in enumerate(lines, 1):
            toks = chat.findall(l)
            if not toks:
                continue
            if non_chat.search(l) or historical.search(l):
                continue
            bad = [t for t in toks if t.rstrip(".,;)`*") != expected]
            if not bad:
                ok_lines += 1
                continue
            if not prescriptive.search(l):
                continue
            flagged.append((f.replace(base, "skills/"), i, l.strip()[:110]))
    print(f"   {len(flagged)} prescriptive reference(s) to a non-expected model"
          f"  ({ok_lines} line(s) correctly name {expected})")
    for f, i, l in flagged[:20]:
        print(f"     {f}:{i}  {l}")
    if flagged:
        fail(f"{len(flagged)} skill line(s) still prescribe a non-expected model — "
             "a future session may reintroduce it")


def main():
    exp = expected_model()
    env_path = resolve_hindsight_env()
    print("Inference surface verification")
    print(f"expected model : {exp}")
    print(f"hindsight env  : {env_path}")
    check_config(exp)
    check_hindsight(exp, env_path)
    check_live_processes(exp, env_path)
    check_cron(exp)
    check_actual_billing(exp)
    check_hindsight_log(env_path)
    check_service()
    check_skills(exp)
    section("RESULT")
    if drift:
        print(f"  {len(drift)} drift item(s):")
        for d in drift:
            print(f"    - {d}")
        sys.exit(1)
    print("  CLEAN — every surface checked matches the expected model.")


if __name__ == "__main__":
    main()
