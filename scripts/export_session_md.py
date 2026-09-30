#!/usr/bin/env python3
"""Export Hermes sessions to readable markdown (session.md files).

Sources:
  1. ~/.hermes/sessions/session_*.json      - JSON session snapshots (legacy + gateway)
  2. ~/.hermes/sessions/*.jsonl             - JSONL transcripts
  3. ~/.hermes/state.db sessions/messages   - canonical store (newest sessions)

Output: ~/.hermes/sessions-md/<session_id>.md  (flat, one file per session)

Incremental: only re-exports when source is newer than the .md output.
Run before the daily backup-sync so markdown lands in GitHub alongside raw data.
"""
import json, sqlite3, glob, os, re, sys, html

HERMES = os.path.expanduser('~/.hermes')
OUT_DIR = os.path.join(HERMES, 'sessions-md')
os.makedirs(OUT_DIR, exist_ok=True)

# Session id -> last activity timestamp (epoch seconds), used for incremental skip
exported = {}  # out_path -> source_mtime

def clean(text):
    if text is None:
        return ''
    s = str(text)
    # strip out reasoning duplication
    return s

def fmt_ts(ts):
    """epoch float or ISO string -> readable"""
    if ts is None:
        return ''
    try:
        import datetime
        if isinstance(ts, (int, float)):
            return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M UTC')
        return str(ts)[:16].replace('T', ' ')
    except Exception:
        return str(ts)

def render(title, meta_lines, msgs, out_path):
    lines = [f'# {title}', '']
    lines.extend(meta_lines)
    lines.extend(['', '---', ''])
    for role, ts, content in msgs:
        if not content or not str(content).strip():
            continue
        c = clean(content)
        # collapse very long tool/system dumps
        if len(c) > 12000:
            c = c[:12000] + f'\n\n_[truncated, {len(str(content))} chars total]_'
        label = {'user': '👤 User', 'assistant': '🤖 Assistant', 'tool': '🔧 Tool',
                 'session_meta': 'ℹ️ Meta', 'system': '⚙️ System'}.get(role, role)
        lines.append(f'### {label} — {fmt_ts(ts)}')
        lines.append('')
        lines.append(c)
        lines.append('')
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

def export_snapshot(path):
    """session_*.json snapshot format"""
    try:
        d = json.load(open(path))
    except Exception:
        return False
    sid = d.get('session_id') or os.path.basename(path).replace('session_', '').replace('.json', '')
    msgs_src = d.get('messages', [])
    msgs = [(m.get('role'), m.get('timestamp'), m.get('content')) for m in msgs_src]
    meta = [
        f"- **Session:** `{sid}`",
        f"- **Platform:** {d.get('platform', '?')}",
        f"- **Model:** {d.get('model', '?')}",
        f"- **Started:** {fmt_ts(d.get('session_start'))}",
        f"- **Last activity:** {fmt_ts(d.get('last_updated'))}",
        f"- **Messages:** {len(msgs_src)}",
    ]
    out = os.path.join(OUT_DIR, f'session_{sid}.md')
    # incremental: skip if unchanged
    src_mtime = os.path.getmtime(path)
    if os.path.exists(out) and os.path.getmtime(out) >= src_mtime:
        return False
    title = f'Session {sid}'
    render(title, meta, msgs, out)
    os.utime(out, (src_mtime, src_mtime))
    return True

def export_jsonl(path):
    """*.jsonl transcript format"""
    base = os.path.basename(path)[:-len('.jsonl')]
    out = os.path.join(OUT_DIR, f'transcript_{base}.md')
    src_mtime = os.path.getmtime(path)
    if os.path.exists(out) and os.path.getmtime(out) >= src_mtime:
        return False
    meta_d, msgs = {}, []
    try:
        with open(path) as f:
            for line in f:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                role = m.get('role')
                if role == 'session_meta':
                    meta_d = m
                    continue
                msgs.append((role, m.get('timestamp'), m.get('content')))
    except Exception:
        return False
    sid = base
    meta = [
        f"- **Session:** `{sid}`",
        f"- **Platform:** {meta_d.get('platform', '?')}",
        f"- **Model:** {meta_d.get('model', '?')}",
        f"- **Messages:** {len(msgs)}",
    ]
    render(f'Transcript {sid}', meta, msgs, out)
    os.utime(out, (src_mtime, src_mtime))
    return True

def export_state_db():
    """Canonical store sessions (newest, may not have jsonl yet)."""
    db_path = os.path.join(HERMES, 'state.db')
    if not os.path.exists(db_path):
        return 0
    out_db = os.path.join(OUT_DIR, 'state.db.markers')
    n = 0
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cur = con.cursor()
    sessions = cur.execute(
        "SELECT id, source, display_name, title, model, started_at, message_count FROM sessions"
    ).fetchall()
    for sid, source, display, title, model, started, mcount in sessions:
        out = os.path.join(OUT_DIR, f'db_{sid}.md')
        msgs_raw = cur.execute(
            "SELECT role, timestamp, content FROM messages WHERE session_id=? AND role IN ('user','assistant') ORDER BY id",
            (sid,)).fetchall()
        msgs = [(r, t, c) for r, t, c in msgs_raw]
        meta = [
            f"- **Session:** `{sid}`",
            f"- **Source:** {source}",
            f"- **Title:** {title or display or '-'}",
            f"- **Model:** {model or '?'}",
            f"- **Started:** {fmt_ts(started)}",
            f"- **Messages:** {mcount}",
        ]
        # marker includes latest message id for incremental
        last_id = cur.execute("SELECT MAX(id) FROM messages WHERE session_id=?", (sid,)).fetchone()[0] or 0
        marker = f'{out}.marker'
        if os.path.exists(marker):
            try:
                if int(open(marker).read().strip()) >= last_id:
                    continue
            except Exception:
                pass
        render(f'Session {sid}', meta, msgs, out)
        with open(marker, 'w') as f:
            f.write(str(last_id))
        n += 1
    con.close()
    return n

def main():
    exported_n = 0
    # 1. state.db
    exported_n += export_state_db()
    # 2. json snapshots
    for p in glob.glob(os.path.join(HERMES, 'sessions', 'session_*.json')):
        if 'request_dump' in p:
            continue
        if export_snapshot(p):
            exported_n += 1
    # 3. jsonl transcripts
    for p in glob.glob(os.path.join(HERMES, 'sessions', '*.jsonl')):
        if export_jsonl(p):
            exported_n += 1
    total = len(glob.glob(os.path.join(OUT_DIR, '*.md')))
    print(f'exported {exported_n} new/updated, total {total} session.md files in {OUT_DIR}')

if __name__ == '__main__':
    main()