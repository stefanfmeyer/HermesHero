# Docker Deployment of Hermes Agent on a Shared Server

Verified Aug 2026 — deploying Pragmatic agent to at-2 (the company monitoring server).

## When This Applies

After creating a clean repo copy (see `clean-repo-copy-checklist.md`), the next step is
deploying the agent to a server. When the server already runs other services (production
apps, databases, Supabase stacks), a self-contained Docker container is the safest deployment
strategy — isolated network, dedicated volumes, no host-level package conflicts.

## Pre-Deployment Server Survey (CRITICAL)

Before deploying, inventory EVERYTHING already running on the target server. The user
explicitly required: "ensure that nothing that is present on at-2 is touched or modified
outside of what I've asked you to do."

```bash
ssh <server> "
  echo '=== Docker containers ===' && sudo docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
  echo '=== Listening ports ===' && sudo ss -tlnp | grep -v '127.0.0.53'
  echo '=== Home dir ===' && ls -la ~
  echo '=== /opt ===' && ls /opt/ 2>/dev/null
  echo '=== Disk ===' && df -h
  echo '=== Memory ===' && free -h
  echo '=== Docker version ===' && docker --version
  echo '=== Docker Compose ===' && docker compose version
  echo '=== Python ===' && python3 --version
  echo '=== Node ===' && node --version
  echo '=== Sudo ===' && sudo -n true 2>&1 && echo 'sudo NOPASSWD' || echo 'sudo needs password'
"
```

Record ALL used ports. Choose your container ports to avoid conflicts. In the at-2 case,
used ports were: 22, 80, 443, 8080, 8081, 8443, 8444, 9100, 9443, 5432, 54321-54327.
Port 8644 (Hermes webhook default) was free.

## Dockerfile Pattern

```dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV HERMES_HOME=/home/pragmatic/.hermes

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git git-lfs build-essential pkg-config libssl-dev libffi-dev \
    python3 python3-pip python3-venv python3-dev \
    nodejs npm postgresql-client jq ripgrep ca-certificates gnupg \
    openssh-client tmux less sudo \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash pragmatic
USER pragmatic
WORKDIR /home/pragmatic

# Install Hermes Agent via official installer
RUN curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Copy repo contents into ~/.hermes/
COPY --chown=pragmatic:pragmatic skills/ ${HERMES_HOME}/skills/
COPY --chown=pragmatic:pragmatic memories/ ${HERMES_HOME}/memories/
COPY --chown=pragmatic:pragmatic scripts/ ${HERMES_HOME}/scripts/

# Runtime directories
RUN mkdir -p ${HERMES_HOME}/sessions ${HERMES_HOME}/logs ${HERMES_HOME}/cache ${HERMES_HOME}/cron ${HERMES_HOME}/hindsight

COPY --chown=pragmatic:pragmatic docker-entrypoint.sh /home/pragmatic/docker-entrypoint.sh
RUN chmod +x /home/pragmatic/docker-entrypoint.sh

EXPOSE 8644
ENTRYPOINT ["/home/pragmatic/docker-entrypoint.sh"]
```

Key decisions:
- **Ubuntu 24.04** base (not Alpine) — Hermes install script expects a full Debian-like env
- **Dedicated user** (`pragmatic`) — not root, matches production hygiene
- **`HERMES_HOME` env var** — so Hermes tools resolve to the correct home inside the container
- **PostgreSQL client** included for Hindsight connectivity (server is in a separate container)

## docker-compose.yml Pattern

```yaml
services:
  pragmatic-postgres:
    image: postgres:16-alpine
    container_name: pragmatic-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: hindsight
      POSTGRES_USER: pragmatic
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pragmatic-pg-data:/var/lib/postgresql/data
    networks:
      - pragmatic-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pragmatic -d hindsight"]
      interval: 5s
      timeout: 5s
      retries: 10

  pragmatic:
    build: .
    container_name: pragmatic
    restart: unless-stopped
    depends_on:
      pragmatic-postgres:
        condition: service_healthy
    environment:
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
      HINDSIGHT_DB_HOST: pragmatic-postgres
      HINDSIGHT_DB_PASSWORD: ${POSTGRES_PASSWORD}
      SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
      SLACK_APP_TOKEN: ${SLACK_APP_TOKEN}
      LINEAR_API_KEY: ${LINEAR_API_KEY}
      WEBHOOK_SECRET: ${WEBHOOK_SECRET}
    volumes:
      - pragmatic-data:/home/pragmatic/.hermes
      - pragmatic-ssh:/home/pragmatic/.ssh
    ports:
      - "8644:8644"
    networks:
      - pragmatic-net

volumes:
  pragmatic-pg-data:
  pragmatic-data:
  pragmatic-ssh:

networks:
  pragmatic-net:
    driver: bridge
    name: pragmatic-net
```

Key decisions:
- **Dedicated Docker network** (`pragmatic-net`) — isolated from other compose stacks
- **Named volumes** for persistence across container rebuilds
- **PostgreSQL in its own container** — not sharing the host PG or other stacks' PG
- **healthcheck** on PostgreSQL — the `pragmatic` container waits for DB readiness
- **SSH key volume** — separate volume so SSH keys survive container rebuilds

## Entrypoint Script

```bash
#!/bin/bash
set -e
export HERMES_HOME=/home/pragmatic/.hermes

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if pg_isready -h pragmatic-postgres -U pragmatic -q 2>/dev/null; then
        echo "PostgreSQL is ready."
        break
    fi
    sleep 1
done

# Start Hermes gateway
echo "Starting Hermes Agent gateway..."
exec hermes gateway run
```

## .env.example Template

```bash
OPENROUTER_API_KEY=sk-or-v1-REPLACE_ME
POSTGRES_PASSWORD=CHANGE_ME
SLACK_BOT_TOKEN=xoxb-REPLACE_ME
SLACK_APP_TOKEN=xapp-REPLACE_ME
LINEAR_API_KEY=lin_REPLACE_ME
GIT_USER_NAME=Pragmatic
GIT_USER_EMAIL=pragmatic@example.com
WEBHOOK_SECRET=REPLACE_ME
```

**Gitignore**: Ensure `.env` is gitignored but `.env.example` is NOT:
```
.env
.env.*
!.env.example
```

## SSH Key for Git Clone on the Server

The server needs its own SSH key to clone the repo from GitHub. Generate it on the server:

```bash
ssh <server> "ssh-keygen -t ed25519 -C 'pragmatic@example.com' -f ~/.ssh/id_ed25519 -N '' && cat ~/.ssh/id_ed25519.pub"
```

Give the public key to whoever has access to the GitHub org to add as a deploy key or to
the Pragmatic GitHub account's SSH keys.

**Pitfall**: Fresh servers don't have GitHub's host key in `known_hosts`. The `git clone`
will fail with "Host key verification failed." Add it first:
```bash
ssh <server> "ssh-keyscan github.com >> ~/.ssh/known_hosts"
```
This command may need user approval in Hermes (it's a network-affecting command).

## GitHub Repo Transfer (Personal → Org)

When transferring a repo from a personal GitHub account to an org:

1. **Update the remote URL** to use the org's SSH host alias:
   ```bash
   git remote set-url origin git@github.com-the company:the company/pragmatic.git
   ```

2. **Set git identity** to the org's email:
   ```bash
   git config user.name "Your Name"
   git config user.email "you@example.com"
   ```

3. **Push to the new remote**:
   ```bash
   git push -u origin main
   ```

4. **Verify no references to the old repo** remain:
   ```bash
   grep -rn "yourusername\|github.com/yourusername" --include="*.md" --include="*.sh" --include="*.py" --include="*.yaml" .
   ```

## Deployment Sequence

1. Clone repo to server (or to a deploy directory)
2. Create `.env` from `.env.example`, fill in real values
3. `docker compose build && docker compose up -d`
4. Verify: `docker logs pragmatic -f` (watch for gateway startup)
5. Verify: `docker exec pragmatic hermes doctor`
6. Configure Slack credentials (can be added to `.env` and container restarted)
7. Set up GitHub webhooks pointing to `http://<server>:8644/webhooks/<name>`

## Model Configuration

For OpenRouter with a GLM model (`glm-5.2` is historical — banned as of 2026-09-20; current sanctioned default is `glm-5.3-flash:cloud` via `https://ollama.com/v1`), the `config.yaml` inside the container needs:
```yaml
model:
  default: thudm/glm-5.2   # HISTORICAL example only — do not use
  provider: openrouter
```

The `OPENROUTER_API_KEY` env var is picked up automatically by Hermes.

## Pitfalls

- **Don't use port 5432 for the PostgreSQL container** — the host may already have
  PostgreSQL running on 5432 (at-2 did). The container's PG is on the Docker network
  only, not exposed to the host, so this is fine — but be aware of it.
- **`ssh-keyscan` may be blocked by Hermes approval** — it's a network command. Either
  get user approval or use `StrictHostKeyChecking=accept-new` on the SSH command itself.
- **Container rebuilds lose `~/.hermes` state unless using volumes** — always mount
  named volumes for `~/.hermes` and `~/.ssh` so sessions, config, and keys persist.
- **The Hermes install script creates a venv inside the container** — this is fine,
  but it makes the image larger. Accept the trade-off for reliability.
- **Don't expose the PostgreSQL container port to the host** — keep it on the Docker
  network only. The Hermes container connects via the service name `pragmatic-postgres`.