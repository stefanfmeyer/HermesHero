---
name: neon-postgres-prisma-debug
description: Debug and fix Neon PostgreSQL + Prisma issues — prisma db execute limitations, URL parsing, pg client patterns
---
# Neon Postgres + Prisma Debug Skill

Common issues when working with Neon PostgreSQL + Prisma, and how to fix them.

## Prisma db execute limitation

`npx prisma db execute --stdin` does **NOT** return SELECT query results. It only executes DDL (CREATE TABLE, INSERT, etc.) and returns "Script executed successfully." It cannot be used to fetch data.

**Workaround**: Use the `pg` npm package directly instead of Prisma for data queries.

```javascript
const { Pool } = require('pg');
const pool = new Pool({
  host, port: 5432, database: db, user, password: pw,
  ssl: { rejectUnauthorized: false }, max: 2
});
const res = await pool.query('SELECT * FROM signals');
await pool.end();
return res.rows; // array of objects
```

## Neon DATABASE_URL parsing

The full Neon DATABASE_URL contains query params after the DB name:
```
postgresql://user:pw@host/dbname?sslmode=require&channel_binding=require
```

When parsing manually, **strip the query params** before matching:
```javascript
const raw = fs.readFileSync('.env', 'utf8').split('DATABASE_URL=')[1].split('\n')[0].trim();
const baseUrl = raw.split('?')[0]; // strip query params
const m = baseUrl.match(/postgresql:\/\/([^:]+):([^@]+)@(.+)\/(.+)/);
```

## Prisma model @@map and quoted table names

If the Prisma schema has `@@map("signals")`, the actual table name is lowercase `signals`, NOT `"Signal"` or `"signals"` (quoted/case-sensitive). Always use unquoted lowercase in SQL:
```sql
SELECT * FROM signals WHERE status = 'OPEN'  -- ✅ correct
SELECT * FROM "Signal" WHERE status = 'OPEN' -- ❌ wrong (case-sensitive)
SELECT * FROM "signals" WHERE status = 'OPEN' -- ❌ wrong (case-sensitive)
```

## execSync psql with special chars in password

Neon passwords often contain `&` which bash interprets as background operator. Use single quotes + explicit shell:
```javascript
const cmd = `psql 'host=${host} port=5432 dbname=${db} user=${user} password=${pw} sslmode=require' -t -A -F'|' -c "${sql}"`;
execSync(cmd, { encoding: 'utf8', stdio: ['pipe','pipe','pipe'], shell: '/bin/bash' });
```
Single quotes around the connection string prevent `&` interpretation.

## JSON columns with execSync/psql are unreliable

If a column contains JSON with commas or newlines (e.g. `reasoning TEXT[]` storing JSON arrays), CSV-style parsing with `psql -F'|'` breaks because the JSON content corrupts the delimiter structure. Use `pg` client instead, which returns proper JS objects.

## Always await async pg queries

If `neonQueryResults` is declared `async`, all call sites must `await` it:
```javascript
// Wrong — returns a Promise, not an array
const results = neonQueryResults(sql);

// Correct
const results = await neonQueryResults(sql);
```
Symptoms: `.filter is not a function`, `.forEach is not a function` on what should be an array.

## pgvector on Neon — Prisma Unsupported field pattern

Neon PostgreSQL supports `pgvector` for embedding storage. When using Prisma, vector columns must be declared as `Unsupported("vector(N)")` in the schema:
```prisma
model RAGDocument {
  embedding Unsupported("vector(1536)")?  // 1536 = nomic-embed-text dims
}
```

**Prisma cannot type `Unsupported` fields** — any `create()` or `update()` that includes `embedding` will fail type-checking. Always use `$queryRaw` template literal for vector operations:

```typescript
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

// Insert with vector
const vector = [0.1, -0.3, ...]; // 1536-dim float array
await prisma.$queryRaw`
  INSERT INTO "RAGDocument" (
    "collectionId", "leadId", "chunkIndex", content, "vectorId", embedding
  ) VALUES (
    ${collectionId}, ${leadId}, ${0}, ${content},
    ${`pg_${leadId}_0`},
    vec_from_text(${JSON.stringify(vector)})
  )
`;

// Query with cosine distance (lower = more similar)
const results = await prisma.$queryRaw<Array<{ id: string; content: string; score: number }>>`
  SELECT id, content,
    1 - cosine_distance(embedding, vec_from_text(${JSON.stringify(queryVector)})) AS score
  FROM "RAGDocument"
  WHERE "collectionId" = ${collectionId}
  ORDER BY cosine_distance(embedding, vec_from_text(${JSON.stringify(queryVector)}))
  LIMIT 5
`;
```

**Key functions:**
- `vec_from_text(json_string)` — parse a JSON array string into a pgvector
- `vec_to_string(embedding)` — convert pgvector back to string for display
- `cosine_distance(a, b)` — cosine distance (0 = identical, 2 = opposite); use `1 - cosine_distance(...)` as a similarity score
- Neon connection string must include `?sslmode=require`

**Embedding generation:** Call Ollama Cloud embeddings API (`POST /v1/embeddings` with `nomic-embed-text`) to produce the 1536-dim vector, then store with `$queryRaw` as above.

## Column naming in signals table (T212 project)

```
id, timestamp, ticker, action, llmConf, conf, sentiment, reasoning,
suggestedAmt, priceAt, executed, executedAt, tradeId, status,
closeReason, closedAt, exitPrice, roiPct, holdingDays
```

Note: `roiPct` (not `roi`), `holdingDays` (not `holdDays`), `closeReason` (not `exitReason`).

## Quick DB verification (psql — faster than writing Node scripts)

When verifying Neon DB connectivity or schema, use `psql` directly — it's faster than writing a Node script:

```bash
psql 'postgresql://USER:PASSWORD@HOST-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require' -t -A -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
```

- `USER` = `neondb_owner` (Neon role)
- Find the pooler host in the `POSTGRES_URL` env var (format: `ep-XXXXX-XXXX-pooler.eu-west-2.aws.neon.tech`)
- Use **single quotes** around the full URL — this prevents `&` in the password or channel_binding param from being interpreted as a bash background operator
- `-t` = no table headers, `-A` = unaligned output, `-c` = execute command
- Password: find in the `POSTGRES_URL` env var — format `npg_XXXX`

## Pool cleanup

Always call `pool.end()` in both success and error paths to prevent connection leaks:
```javascript
let pool;
try {
  pool = getPool();
  const res = await pool.query(sql);
  return res.rows;
} catch (e) {
  return [];
} finally {
  if (pool) await pool.end();
}
```
Or in non-async fire-and-forget: `pool.query(sql).then(() => pool.end()).catch(...)`.
