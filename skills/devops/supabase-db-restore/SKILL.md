---
name: supabase-db-restore
description: Restore a Supabase pg_dump text-format backup to a local PostgreSQL instance
tags: [postgresql, supabase, database, backup]
---

# Restore Supabase DB Backup to Local PostgreSQL

## Context
Supabase projects use a specific backup format. Restoring to a local PostgreSQL instance requires careful handling of the dump format and connection settings.

## Prerequisites
- PostgreSQL client tools installed (`psql`, `pg_restore`)
- Local PostgreSQL running (on Mac: `brew services start postgresql`)
- Superuser access to the local PostgreSQL instance
- **Supabase port is 5433** (not the default 5432)

## Supabase Backup Format
Supabase generates pg_dump text-format dumps, NOT pg_restore custom format. This means:
- `pg_restore` will fail with: `input file appears to be a text format dump. Please use psql.`
- Use `psql` directly instead

## Key Discovery
Supabase backups contain `\connect template1` (or `\connect postgres`) commands at the start to set the database context. These MUST be stripped before importing to a custom-named local database, otherwise `psql` tries to run everything against `template1`/`postgres` instead of your target DB.

## Python Subprocess Method (Recommended)

```python
import subprocess, os, re

env = {**os.environ}
env.pop("PGPASSWORD", None)  # don't export empty var

decompressed = "/path/to/backup.sql"

with open(decompressed, 'r') as f:
    content = f.read()

# Strip \connect commands so everything runs against target DB
content = re.sub(r'\\connect\s+\w+\n', '', content)

# Pipe to psql
proc = subprocess.Popen(
    ["psql", "-h", "localhost", "-p", "5433", "-U", "youruser", "-d", "myproject"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    env=env
)
stdout, _ = proc.communicate(input=content)
print(stdout)
```

**Critical:** Use `subprocess.Popen` with `communicate(input=content)` — this pipes SQL to stdin and avoids:
1. Env var conflicts (no `PGPASSWORD=""` in environment)
2. Shell quoting issues with large SQL strings
3. Password prompts being sent to stdin incorrectly

## Step-by-Step

1. Decompress if gzip: `gunzip -c backup.gz > backup.sql`
2. Identify the dump format: `file backup.sql` (should say "ASCII text" for pg_dump text format)
3. Check for `\connect` commands: `grep '\\connect' backup.sql`
4. Strip `\connect` commands with Python
5. Pipe to psql targeting your local database
6. Verify: `psql -h localhost -p 5433 -U youruser -d myproject -c "SELECT COUNT(*) FROM users;"`

## Troubleshooting

- **pg_restore: "input file appears to be a text format dump"** → Not a custom format dump, use psql not pg_restore
- **Connection refused on port 5432** → Supabase/PostgreSQL is on port **5433** (discovered empirically)
- **Empty password doesn't work with `-W`** → Use `PGPASSWORD=""` env var approach, or trust auth via `pg_hba.conf` (local socket auth)
- **DROP DATABASE times out** → Next.js/Prisma holds open connections; kill dev server first
- **psql hangs waiting for password** → Auth method may be `scram-sha-256`; use env var `PGPASSWORD=yourpass` or switch local auth to `trust` in pg_hba.conf
