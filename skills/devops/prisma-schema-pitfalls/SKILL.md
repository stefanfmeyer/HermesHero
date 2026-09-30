---
name: prisma-schema-pitfalls
description: "General Prisma ORM schema syntax pitfalls and build-time fixes — referential action capitalization, upsert by non-id fields, SQLite vs PostgreSQL migration, db push vs migrate. Applies to any Prisma project (not Neon-specific)."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [prisma, database, schema, sqlite, postgresql, build-error]
    related_skills: [neon-postgres-prisma-debug, nextjs-development-patterns]
---

# Prisma Schema Pitfalls

General Prisma ORM issues that cause build failures or `prisma db push` errors. These are syntax-level mistakes that apply to any Prisma project regardless of database provider.

## `onDelete` Referential Action Capitalization

**Error:** `P1012: Invalid referential action: 'cascade'`

```prisma
// ❌ Fails — lowercase 'cascade'
lead Lead @relation(fields: [leadId], references: [id], onDelete: cascade)
```

```prisma
// ✅ Works — capitalized 'Cascade'
lead Lead @relation(fields: [leadId], references: [id], onDelete: Cascade)
```

All referential actions must use PascalCase: `Cascade`, `Restrict`, `SetNull`, `SetDefault`, `NoAction`.

This is easy to miss because Prisma doesn't auto-complete or lint this in all editors, and the error message says "Invalid referential action" without hinting at capitalization.

## `@unique` Required for `upsert` by Non-Id Field

**Error:** `Type '{ email: string; }' is not assignable to type 'LeadWhereUniqueInput'`

**Root cause:** Prisma's `upsert` `where` clause only accepts fields marked `@id` or `@unique`. You cannot upsert by a regular non-unique field.

```prisma
// ❌ Cannot upsert by email — it's not unique
model Lead {
  id    String @id @default(cuid())
  email String
}
```

```prisma
// ✅ Add @unique to enable upsert by email
model Lead {
  id    String @id @default(cuid())
  email String @unique
}
```

After adding `@unique` to a column that already has data, run `npx prisma db push --force-reset` to recreate the table with the constraint. This destroys data — for production, use `prisma migrate` instead.

## SQLite: `db push` vs `migrate dev`

For quick prototypes and conference/event apps using SQLite:

- `npx prisma db push` — syncs schema to DB without migrations. Fast, no migration files. Ideal for prototyping.
- `npx prisma db push --force-reset` — drops and recreates tables. Required when adding `@unique` to a column with existing data. **Destroys all data.**
- `npx prisma migrate dev` — creates migration files. Use when you need a migration history (production, team collaboration).

For SQLite specifically, `db push` is usually sufficient since the database is a local file.

## `db push` Cannot Distinguish a Rename From a Drop-and-Create (SILENT DATA LOSS)

**The trap:** renaming a field in `schema.prisma` is **not** a rename to `prisma db push`. With no migration file carrying the intent, push sees "old column gone, new column appeared" — so it **drops the old column, destroying every value in it**, then adds the new one empty.

```prisma
// Before
model Lead { region String? }

// After — "just a clearer name", and 100% of existing values are gone
model Lead { country String? }
```

This is worst on a project whose **build command** runs push, because it then happens unattended on every deploy. On LGC quiz the Vercel build command is `npx prisma generate && npx prisma db push --accept-data-loss && next build` — the `--accept-data-loss` flag means the wipe executes with no prompt and nothing in the deploy log that reads as a warning.

**Symptom signature:** deploy goes green, pages return 200, but a previously-populated column now reads empty/NULL everywhere and CSV exports silently lose those values. Nothing errors, which is exactly why it ships unnoticed.

**Decision rule — rename the label, not the column:**

| Want | Do this |
|---|---|
| UI or CSV header should read differently | Change only the label/header strings. Keep the Prisma field name. |
| Genuinely must rename the column | Write an explicit `ALTER TABLE ... RENAME COLUMN` yourself and apply it around the push — never let `db push` infer the intent. |
| Adding a new field that should be mandatory | Add it **nullable**, then enforce required at the application layer (form + zod validation). Push stays a safe additive change and existing rows survive. |

**Before any rename on a populated DB:** check whether the field is referenced in a build or push command, and count non-null values first so you know exactly what a mistaken push would cost.

## Prisma Client Regeneration

After ANY change to `prisma/schema.prisma`, you must regenerate the Prisma Client:

```bash
npx prisma generate
```

This updates `node_modules/@prisma/client` with the latest types. Without this, TypeScript will use stale types and your build will fail with type errors about missing or changed fields.

`npx prisma db push` automatically runs `generate` after pushing, but `npx prisma generate` alone is needed when you only change the schema file without pushing (e.g., adding a model you haven't deployed yet).

## Next.js Build Type Errors from Prisma

When `next build` fails with a Prisma-related type error:

1. Check if `npx prisma generate` was run after the last schema change
2. Check if the schema has syntax issues (capitalization, missing `@unique`)
3. Run `npx prisma validate` to check schema validity without touching the DB
4. Restart the TypeScript server / Next.js dev server after regenerating the client (stale types in memory)

## Switching from SQLite to PostgreSQL

For deployment to platforms that don't support SQLite (Vercel, serverless):

```prisma
// Change datasource provider
datasource db {
  provider = "postgresql"  // was "sqlite"
  url      = env("DATABASE_URL")
}
```

Update `.env`:
```
# Was: DATABASE_URL="file:./dev.db"
DATABASE_URL="postgresql://user:password@host:5432/dbname"
```

Then: `npx prisma generate && npx prisma db push`

SQLite-specific types (none in standard Prisma) and `@default(cuid())` / `@default(uuid())` work identically in PostgreSQL.

### Vercel + Neon specifics (learned on LGC quiz migration)

- The provider switch alone is NOT enough on Vercel — the build won't push the schema unless told. Set the Vercel project Build Command to `npx prisma generate && npx prisma db push --accept-data-loss && next build` (safe against an empty Neon DB; `db push` alone doesn't need migration files).
- Neon linked through Vercel's Storage tab injects `DATABASE_URL` (+ `POSTGRES_PRISMA_URL`, pooled/unpooled variants) as **sensitive** env vars — the Vercel API returns them masked even to the owner. You cannot retrieve the connection string for local scripts; the workaround for ad-hoc DB work is the Neon console SQL Editor.
- Symptom of a deploy that still has the SQLite schema against a Postgres URL: pages serve 200 but any DB-backed API returns 500 "Failed to fetch …". Check the deployed build actually ran `prisma generate` after the provider switch (inspect build events via `/v2/deployments/:id/events?builds=1`).
- Prisma provider mismatch is invisible at build time on Vercel — `next build` succeeds because the schema only matters at runtime query time. Always curl a DB-backed endpoint as part of deploy verification.

## Pitfalls Table

| Problem | Cause | Fix |
|---------|-------|-----|
| `P1012: Invalid referential action: 'cascade'` | Lowercase action name | Capitalize: `onDelete: Cascade` |
| `Type '{ X: string }' is not assignable to 'WhereUniqueInput'` | Upsert by non-unique field | Add `@unique` to the field in schema |
| Build fails after schema change | Prisma Client not regenerated | Run `npx prisma generate` |
| `prisma db push` fails on `@unique` addition | Existing data violates uniqueness | Use `--force-reset` (destroys data) or `migrate` |
| Runtime error: missing model property | Schema changed but client not regenerated | `npx prisma generate`, restart dev server |
| `P1012` parse error on relation | Missing space in `onDelete:X` | Use `onDelete: X` with space after colon |
| Adding a new column to SQLite with `db push` | Schema changed but DB not synced | `npx prisma db push` (auto-runs `generate`) — non-destructive for nullable/defaulted columns |
| TypeScript sees stale Prisma types after schema edit | LSP cached old generated client | `npx prisma db push` regenerates client; restart TS server if LSP still shows old types |
| Column values vanish after a field rename | `db push` treated the rename as drop-and-create | Don't rename populated columns — change only the label/header, or hand-write `ALTER TABLE ... RENAME COLUMN` |