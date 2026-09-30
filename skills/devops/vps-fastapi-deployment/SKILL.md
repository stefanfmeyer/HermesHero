---
name: vps-fastapi-deployment
description: Deploy and manage a FastAPI service on a remote VPS via SSH — systemd, logging, debugging, and common pitfalls.
triggers:
  - deploy fastapi to vps
  - systemd service on vps
  - fastapi systemctl restart timeout
  - cce-engine-api
---

# VPS FastAPI Deployment Skill

## SSH Connection
```
Host: root@178.104.152.66
Key: ~/.ssh/openclaw-vps
```

## Golden Rule: Never Use SSH Heredocs for File Content
**Problem:** `ssh 'cat > file << EOF'` mangles multiline Python/content.
**Solution:** Write the file locally, then `scp` to VPS, then execute via SSH Python.

```bash
# WRONG — strings get mangled
ssh -i ~/.ssh/openclaw-vps root@178.104.152.66 'cat > /tmp/script.py << EOF
def foo():
    pass
EOF'

# RIGHT — write locally, upload, execute
scp -i ~/.ssh/openclaw-vps /tmp/script.py root@178.104.152.66:/tmp/script.py
ssh -i ~/.ssh/openclaw-vps root@178.104.152.66 'python3 /tmp/script.py'
```

## Systemd Service Deployment Pattern
**Problem:** `systemctl daemon-reload && systemctl enable ...` chains timeout over SSH.
**Solution:** Write a Python setup script, upload, execute.

```python
# /tmp/vps_systemctl_setup.py — run on VPS
import subprocess

subprocess.run(['cp', '/tmp/cce-engine-api.service', '/etc/systemd/system/'], check=True)
subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, timeout=10)
subprocess.run(['systemctl', 'enable', 'cce-engine-api'], capture_output=True, timeout=15)
print("DONE")
```

Upload via `scp`, then run `python3 /tmp/vps_systemctl_setup.py`.

## Restart Pattern (use this every time)
```python
# /tmp/vps_restart.py
import subprocess

# Clear pycache
subprocess.run(
    "find /home/node/CCE-ENGINE-VPS/api -name __pycache__ -exec rm -rf {} + 2>/dev/null",
    shell=True, capture_output=True, timeout=10
)

# Restart service
r = subprocess.run(['systemctl', 'restart', 'cce-engine-api'], capture_output=True, timeout=20)
print('restart:', r.returncode)

# Verify
import urllib.request
try:
    with urllib.request.urlopen('http://localhost:18789/health', timeout=5) as resp:
        print('health:', resp.read().decode())
except Exception as e:
    print('health error:', e)
```

## Common Pitfalls

### 1. `CORSMwares` typo
```python
# WRONG — crashes server silently
from fastapi.middleware.cors import CORSMwares

# RIGHT
from fastapi.middleware.cors import CORSMMiddleware
```

### 2. Health check field name mismatch
```python
# WRONG — looks for key "ollama", not "ollama_healthy"
ollama_healthy=ollama.get("ollama", False)

# RIGHT
ollama_healthy=ollama.get("ollama_healthy", False)
```

### 3. `ps aux | grep process` matches grep itself
```bash
# WRONG — shows the grep line
ps aux | grep uvicorn

# RIGHT — excludes grep
ps aux | grep uvicorn | grep -v grep
```

### 4. Multiline strings in SSH commands
Always use Python scripts + SCP. Never embed string content directly in SSH commands.

### 5. State not persisting output_content
After `execute_stage()`, `output_content` is read from disk via `get_stage_output_content()` but must be saved back to `state.data`:
```python
output_content = get_stage_output_content(...)
state.data["stage_outputs"][stage_id]["output_content"] = output_content
state.save()  # CRITICAL: without this, output_content is lost
```

### 6. PipelineRunRequest is flat, not nested
```python
# WRONG — handler tried to access body.params
body.params.primary_keyword

# RIGHT — flat model, direct field access
body.primary_keyword
```

## Structured Logging
- Log file: `/var/log/cce-engine-api.log` (100KB max, rotating)
- Format: `%(asctime)s %(levelname)s %(name)s — %(message)s`
- Service stdout/stderr → systemd journal → `journalctl -u cce-engine-api`
- Python `logging` → writes to `/var/log/cce-engine-api.log`

## API Base URL
- **VPS:** `http://178.104.152.66:18789`
- **Health:** `GET /health` (no auth)
- **Stages:** `POST /stages/{1-8}` (auth: `X-API-Key` header)
- **Run:** `POST /run` (background, returns run_id immediately)
- **Status:** `GET /run/{run_id}/status` (reads from disk, survives restarts)

## Verification Checklist
After any deployment:
1. `curl http://localhost:18789/health` → `ollama_healthy` should be `true`
2. `curl http://localhost:18789/` → welcome message
3. Without `X-API-Key` → 401
4. With wrong key → 401
5. `systemctl status cce-engine-api` → active (running)
6. `journalctl -u cce-engine-api --no-pager -n 5` → no errors
