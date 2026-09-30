# Static API Boundary Audit

## Overview

TypeScript validates types within a file but **cannot catch mismatches across architectural boundaries** — where a frontend interface defines one shape and the backend route returns another. This reference documents the systematic technique for finding these bugs by reading code side-by-side.

**When to use:** After TypeScript compiles cleanly but you still suspect bugs. Before or after browser-based `dogfood` testing. Especially in projects where the frontend defines its own data types (client-side interfaces) that don't derive from the API schema.

## The Four Categories of Boundary Bugs

### 1. Data Shape Mismatch

The frontend expects a different nesting structure than the API returns.

**Classic example:**
- API returns `{ data: { items: [...] } }`
- Frontend checks `Array.isArray(json.data)` — but `json.data` is an object `{ items }`, not an array
- Result: `setMeetings([])`, page shows "No meetings" even when meetings exist

**How to find it:** Read the API route handler and the frontend fetch handler simultaneously. Trace what shape `json` actually is vs. what shape the frontend code expects.

### 2. Enum/Constant Drift

The frontend references a value that doesn't exist in the backend schema.

**Classic example:**
- DB enum `AppointmentStatus` has `PENDING`
- Frontend uses `"SCHEDULED"` in status colors, filters, and conditional renders
- Result: status badges never match, "upcoming" filter misses all meetings, action buttons never show

**How to find it:**
1. Read the Prisma enum definitions or backend constants
2. Search the frontend for every reference to that enum's values
3. Cross-reference each one — if the frontend uses a value not in the backend, it's a bug

### 3. Missing HTTP Method

The frontend calls an HTTP method that has no route handler.

**Classic example:**
- Frontend calls `PATCH /api/meetings/:id` to update meeting status
- Backend only has `PUT /api/meetings/:id` — no PATCH handler
- Result: 405 Method Not Allowed, status changes silently fail

**How to find it:**
1. Find the frontend's fetch call and note the HTTP method
2. Go to the corresponding API route file
3. Check whether that HTTP verb export exists (`export async function PATCH`)

### 4. Missing Required Fields

A required DB field isn't sent by the frontend but isn't optional on the model.

**Classic example:**
- `Appointment` model requires `clientId String`
- Frontend sends `{ leadId, title, startTime }` — no `clientId`
- Result: Prisma throws a constraint violation on every create

**How to find it:**
1. Read the Prisma model — note all required fields (non-optional, no `@default`)
2. Read the frontend form state / form submission — what fields does it collect?
3. Check the API POST handler — does it derive missing fields from context?

## Systematic Audit Checklist

For each API route → frontend page pair:

- [ ] **Data shape:** Read the API response JSON structure. Does the frontend parsing match?
- [ ] **Enum values:** Extract all enum/constant values from the backend. Do they match every frontend reference?
- [ ] **HTTP methods:** For every fetch call, does a matching handler exist in the route file?
- [ ] **Required fields:** For every POST/PUT, does the frontend send all required schema fields?
- [ ] **Relation includes:** If the frontend accesses a relation (e.g. `meeting.lead`), does the route handler `include` it?
- [ ] **Null safety:** Are there `?.` operators or fallbacks for nullable relation fields the frontend reads?

## Automation Ideas

This is a human-reading technique, but you can automate parts:

```bash
# Find all enum references in frontend code
grep -rn "SCHEDULED\|PENDING\|CONFIRMED\|CANCELLED\|COMPLETED" apps/web/app/ --include="*.tsx" --include="*.ts"

# Find all PATCH calls in frontend
grep -rn "method:.*PATCH\|PATCH" apps/web/app/(app)/ --include="*.tsx"

# List all exported HTTP methods in API routes
for f in apps/web/app/api/**/route.ts; do
  methods=$(grep -E "^export async function (GET|POST|PUT|PATCH|DELETE)" "$f" | awk '{print $NF}')
  echo "$f: $methods"
done
```

## Origin

This technique was formalized on 2026-05-15 during a double-check of a full-app audit on the Nexus project (Next.js + Prisma + Fastify monorepo). Four real bugs were found that TypeScript's type checker missed entirely:

| # | Category | Bug | Found Via |
|---|----------|-----|-----------|
| 1 | Data Shape | `data.items` vs `Array.isArray(data)` mismatch | Read API handler + frontend fetch side-by-side |
| 2 | Enum Drift | Frontend uses `SCHEDULED`, DB has `PENDING` | Cross-referenced enum values |
| 3 | Missing Method | Frontend calls `PATCH`, route only has `PUT` | Grep for method calls vs route exports |
| 4 | Missing Field | `clientId` required but not sent | Checked model required fields vs form payload |
