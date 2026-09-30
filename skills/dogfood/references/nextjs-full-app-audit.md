# Full Next.js App Audit (Server-Side)

## Overview

Browser-based QA (dogfood) catches frontend issues. This reference covers the **server-side audit** — checking every API route, every page route, auth protection, and the build pipeline. Run this in parallel with or before browser testing.

## Why This Matters

Next.js has a unique failure mode: pages and API routes can compile fine but crash at runtime or during static generation. TypeScript won't catch:
- Missing API route handlers (frontend calls a route that doesn't exist)
- Auth checks omitted from unprotected routes
- Cookie-reading in static contexts (prerender crash)
- Data shape mismatches between frontend fetch and API response
- Stub routes that need real implementation

## The Audit Checklist

### Phase 1: Discover

```bash
# All page files
find app -name "page.tsx" | sort

# All API route files
find app/api -name "route.ts" | sort

# All layouts (check for auth protection)
find app -name "layout.tsx" | sort

# All server actions
find app -name "actions.ts" | sort
```

### Phase 2: API Route Audit

For each route in `app/api/`, check:

- **Auth protection** — Does it call `getUser()` and return 401 if null?
- **Error handling** — Does it wrap the body in try/catch returning 500?
- **Correct HTTP methods** — Does every `export async function` match what the frontend calls?
- **Auth-free routes** — Only `webhook`, `robots.txt`, `sitemap.xml` should be unprotected
- **Stub readiness** — If the route returns empty data (stub), does the frontend handle it gracefully (empty state UI, not a crash)?

### Phase 3: Page Route Audit

For each page route (non-API), check:

- **Public pages** (login, sign-up, public content) — Should return 200
- **Protected pages** (dashboard, settings, team, etc.) — Should 307 redirect to sign-in
- **Auth callback** — Should handle OAuth redirects correctly
- **Onboarding** — Should check `onboardingCompletedAt` and redirect accordingly

Test them all:
```bash
for path in "/api/user" "/api/team" "/sign-in" "/dashboard" "/onboarding"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000$path")
  echo "$code $path"
done
```

### Phase 4: Static Generation Check

Pages that read cookies (auth-protected layouts) will crash during `next build` static generation:

```typescript
// BROKEN — crashes during build:
export default async function Layout({ children }) {
  const user = await getUser(); // reads cookies — fails in static context
}

// FIXED:
export const dynamic = 'force-dynamic';
export default async function Layout({ children }) {
  const user = await getUser();
}
```

Run `npm run build` and check the output. If you see `Error occurred prerendering page`, the page needs `force-dynamic`.

### Phase 5: Build Verification

```bash
# Full build — check for:
# 1. TypeScript errors
# 2. Prerender errors
# 3. Missing module errors
npm run build 2>&1 | grep -E "Type error|error TS|prerender|Error occurred prerendering|Module.*not found"
```

### Phase 6: Auth Flow Test

Test the full auth lifecycle structurally (not with real login credentials):

1. Check that `/dashboard` redirects unauthenticated users to `/sign-in`
2. Check that `/api/user` returns 401 for unauthenticated requests
3. Check that the sign-in form renders (200, no JS errors)
4. Check that the sign-up form renders
5. Check that the sign-out action exists and clears the session
6. Check that the auth callback route works (returns appropriate redirect even without a real code)

## Common Findings

| Finding | Likely Cause | Fix |
|---------|-------------|-----|
| API route returns data without auth | Missing `getUser()` check at top of handler | Add `if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })` |
| Dashboard page crashes during build | Layout reads cookies without `force-dynamic` | Add `export const dynamic = 'force-dynamic'` |
| Page shows empty state but should show data | API route doesn't exist or returns null | Create the route or stub it |
| Google OAuth redirects back with error | Auth callback still uses old auth provider (Supabase) | Rewrite callback route for new provider |
| Social suite page fetches /api/social/accounts and gets 404 | Route doesn't exist | Create stub route returning `{ accounts: [] }` |
| Polar portal route uses wrong lookup | Gets team by `user.id` instead of `team.polarCustomerId` | Fix: get team via `getUserWithTeam()`, then read `team.polarCustomerId` |
| npm audit shows vulnerabilities | Build-time-only deps (vercel CLI chain) | Mark as won't-fix unless it breaks CI |

## Order of Operations

1. **Discover** all routes (Phase 1)
2. **Audit API routes** — add missing auth checks, fix bugs (Phase 2)
3. **Audit page routes** — identify missing stubs (Phase 3)
4. **Fix build** — add `force-dynamic` to auth-protected layouts (Phase 4)
5. **Verify build** passes cleanly (Phase 5)
6. **Test auth flow** structurally (Phase 6)
7. **Browser test** critical pages with dogfood workflow
8. **Commit** with message prefix "fix: full audit — "

## Origin

Formalized from a 2026-05-15 audit of a client project (a Next.js 16 + Neon Auth + Polar payments app). Findings included: 4 API routes missing auth checks, 1 Polar portal bug (wrong customer ID lookup), 1 static generation crash (missing force-dynamic), 2 missing social API stubs, 1 outdated Supabase OAuth callback.
