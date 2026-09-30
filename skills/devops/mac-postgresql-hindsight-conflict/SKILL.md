---
name: mac-postgresql-hindsight-conflict
description: Resolve PostgreSQL port conflict when hindsight-embed runs its own PG instance on Mac
tags: [postgresql, mac, hindsight, homebrew]
author: yourusername
---

# Mac PostgreSQL + Hindsight-Embed Conflict

## Problem
On Stef's Mac Mini M4, `hindsight-embed` runs its own PostgreSQL 16 instance that:
- Occupies port 5432 (TCP and Unix socket)
- Uses `password` auth (not `trust`)
- Can't be stopped/restarted via launchctl (Bootstrap fails with I/O error)
- `brew services start postgresql@16` also fails (launchctl bootstrap gui/501 error)

This means a "clean" PostgreSQL 16 install via Homebrew cannot bind to port 5432.

## Solution: Use PostgreSQL 15 on port 5433

PostgreSQL 15 is installed (idle, not managed by launchctl) and works correctly.

### Step 1: Start PostgreSQL 15 on port 5433
```bash
LC_ALL="en_US.UTF-8" /opt/homebrew/Cellar/postgresql@15/15.17/bin/pg_ctl -D /opt/homebrew/var/postgresql@15/ start -o "-p 5433"
```

> **CRITICAL:** Without `LC_ALL="en_US.UTF-8"`, the server fails with: `FATAL: postmaster became multithreaded during startup`

### Step 2: Create database
```bash
/opt/homebrew/Cellar/postgresql@15/15.17/bin/psql -h localhost -p 5433 -U openstef -d postgres -c "CREATE DATABASE nexus;"
```

### Step 3: Verify connection
```bash
/opt/homebrew/Cellar/postgresql@15/15.17/bin/psql -h localhost -p 5433 -U openstef -d nexus -c "SELECT 1;"
```

### Step 4: Update DATABASE_URL in project
```
DATABASE_URL="postgresql://openstef@localhost:5433/nexus?schema=public"
```

### Verify PostgreSQL is running
```bash
pg_isready -h localhost -p 5433
# Expected: localhost:5433 - accepting connections
```

## Why this happens
- `hindsight-embed-hermes` (PID 35350 on Stef's machine) starts its own PG instance at `/Users/openstef/.pg0/instances/hindsight-embed-hermes/data/`
- That instance's `pg_hba.conf` uses `password` auth — no way to change without restarting it
- Homebrew's PG16 also tries to use the same ports, causing conflicts

## If you need to stop PG15 later
```bash
/opt/homebrew/Cellar/postgresql@15/15.17/bin/pg_ctl -D /opt/homebrew/var/postgresql@15/ stop
```
