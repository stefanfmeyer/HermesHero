---
name: nextauth-auth-patterns
description: NextAuth authentication patterns — credentials providers with and without database adapters, NextAuth v5 Edge middleware, Prisma 7 + Neon adapter setup, and auth debugging for Next.js App Router projects.
trigger: Setting up NextAuth authentication, debugging JWT/session issues, configuring credentials provider, integrating Neon Auth, or debugging silent auth failures in Edge middleware.
tags: [nextauth, auth, neon, prisma, credentials, edge, jwt, middleware]
---

# NextAuth Auth Patterns

NextAuth v4/v5 credentials-only auth patterns for Next.js App Router. Covers JWT-only setup (no DB adapter), Prisma 7 + Neon adapter, Edge middleware debugging, and common pitfalls.

## Core Principle: No Adapter for Credentials-Only

NextAuth credentials-only auth with JWT sessions does **NOT** need a database adapter. The session is a stateless JWT cookie — no DB session/account tables required.

**When to NOT use PrismaAdapter:**
- Credentials-only auth (no OAuth, no email verification)
- JWT session strategy (not database sessions)
- Any setup where you manage users in your own DB

Using `PrismaAdapter(prisma)` with credentials-only auth causes hangs/timeouts with Neon because each auth attempt makes multiple DB round-trips that block the Node event loop.

---

## NextAuth v5 Credentials + Neon DB (Prisma 7)

### Auth Options (`src/lib/auth/auth.ts`)

```typescript
import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { compare } from "bcryptjs";

const ADMIN_EMAIL = "your@email.com";
const ADMIN_PASSWORD_HASH = "paste_hash_from_step_1_here";

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  pages: { signIn: "/login", error: "/login" },
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        if (credentials.email.toLowerCase() !== ADMIN_EMAIL) return null;
        const valid = await compare(credentials.password, ADMIN_PASSWORD_HASH);
        if (!valid) return null;
        return { id: "1", email: ADMIN_EMAIL, name: "Admin" };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.id = user.id;
      return token;
    },
    async session({ session, token }) {
      if (session.user) (session.user as any).id = token.id as string;
      return session;
    },
  },
};
```

### Auth Route (`src/app/api/auth/[...nextauth]/route.ts`)

```typescript
import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth/auth";

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
```

### Pre-compute bcrypt hash
```bash
cd ~/your-project
node -e "const bcrypt = require('bcryptjs'); bcrypt.hash('YOUR_PASSWORD', 12).then(h => console.log(h))"
```

---

## NextAuth v5 — Cookie Name, Edge Middleware, and `getToken()` Salt

NextAuth v5 changes the session cookie name prefix from `__Secure-next-auth.session-token` (v4) to `__Secure-authjs.session-token` (v5). This matters for `getToken()` in Edge middleware.

**Critical: `getToken` salt must match the actual cookie name including prefix.**

```typescript
// ✅ Correct — salt equals the full cookie name with __Secure- prefix
const token = await getToken({
  req,
  secret: process.env.AUTH_SECRET,
  salt: "__Secure-authjs.session-token",
  secureCookie: true,
});

// ❌ Wrong — missing prefix; getToken defaults to "authjs.session-token" without secureCookie
// and decryption silently returns null, so every protected route redirects to /signin
```

**Edge middleware crash (silent failure):** `middleware.ts` runs in Vercel Edge Runtime. Importing anything with Node.js dependencies (`prisma`, `bcryptjs`) crashes silently — no output, no logs. The cookie IS present in DevTools, but `req.auth` is undefined → every protected route redirects to `/signin`.

**Fix:** Use `getToken` from `next-auth/jwt` in middleware. It decodes JWTs with Web Crypto (available in Edge), needs only `AUTH_SECRET`:

```typescript
// middleware.ts — Edge-safe, no Node.js imports
import { getToken } from "next-auth/jwt";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(req: NextRequest) {
  const { nextUrl } = req;

  const isPublicRoute =
    nextUrl.pathname === "/" ||
    nextUrl.pathname === "/signin" ||
    nextUrl.pathname === "/signup" ||
    nextUrl.pathname.startsWith("/api/webhooks") ||
    nextUrl.pathname === "/api/health";

  if (isPublicRoute || nextUrl.pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  const token = await getToken({
    req,
    secret: process.env.AUTH_SECRET,
    salt: "__Secure-authjs.session-token",
    secureCookie: true,
  });

  if (!token) {
    if (nextUrl.pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/signin", nextUrl));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

**Probing when auth silently fails:**
```typescript
// Quick probe: does the cookie even reach the server?
const cookie = req.cookies.get("__Secure-authjs.session-token");
console.log("cookie present:", !!cookie?.value, "length:", cookie?.value?.length);
```

If `cookie` is undefined, the cookie is dropped before reaching the server (check `NEXTAUTH_URL` and domain). If present but `getToken` still returns null, the salt or `AUTH_SECRET` is wrong.

---

## Prisma 7 + Neon Adapter Setup

### Problem
Prisma 7 defaults to a WASM engine (`engineType = "client"`) that requires a driver adapter. Using the Neon TCP pooler directly with `neon()` query function fails with:
```
TypeError: Cannot connect using a plain NeonQueryFunction to PoolConfig
```

### Solution — Full adapter stack

**1. Install dependencies**
```bash
npm install --save @neondatabase/serverless @prisma/adapter-neon
```

**2. prisma/schema.prisma**
```prisma
generator client {
  provider = "prisma-client-js"
  // No engineType — defaults to WASM, requires adapter
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

**3. src/lib/prisma.ts**
```typescript
import { PrismaClient } from "@prisma/client";
import { PrismaNeon } from "@prisma/adapter-neon";
import { Pool } from "@neondatabase/serverless";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

function createPrismaClient() {
  const pool = new Pool({ connectionString: process.env.DATABASE_URL! });
  const adapter = new PrismaNeon(pool as any);
  return new PrismaClient({ adapter } as any);
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();
if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
```

Key: `pool as any` is required because the TS types for `Pool` and `PoolConfig` don't align between packages.

**4. DATABASE_URL in .env**
```
DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
```

### Gotchas
- Do NOT use `new Pool(urlString)` — must use `new Pool({ connectionString: urlString })`
- `engineType = "library"` does NOT work with Neon TCP pooler in Prisma 7 — only the WASM + adapter approach works
- `neon()` query function (HTTP) works for casual queries but Prisma needs the `Pool` (WebSocket) for transactional workloads

---

## Vercel Deployment — Auth Env Vars Checklist

| Variable | Source |
|---|---|
| `AUTH_SECRET` | `openssl rand -hex 32` |
| `NEXTAUTH_URL` | exact deployed URL e.g. `https://nexus-ng-rouge.vercel.app` |
| `NEXT_PUBLIC_API_URL` | same |
| `DATABASE_URL` | Neon PostgreSQL connection string |

**`trustHost: true` is REQUIRED** for NextAuth v5 on Vercel:
```typescript
trustHost: true,
secret: process.env.AUTH_SECRET,
```

`trustHost` is only valid in NextAuth v5 (Auth.js). On v4 it is a TypeScript error. v5's default host verification rejects cross-origin callbacks if `trustHost` is not set and the host header doesn't match `NEXTAUTH_URL`.

---

## Migration from Supabase Auth

1. Remove `@supabase/ssr` and `@supabase/supabase-js` from package.json
2. Install `@neondatabase/auth`
3. Delete `lib/supabase/` directory
4. Replace `app/auth/callback/route.ts` with Neon Auth version
5. Replace all imports: `signInWithPassword` → `signIn.email`, `signUp` → `signUp.email`
6. Add `neonUserId` to users table schema
7. Rewrite `getUser()` to verify JWT from cookie, then lookup by `neonUserId`

For full Neon Auth integration details, see the `third-party-api-integration` skill — it covers server-side client patterns, credential storage, and API route proxies that apply to auth integration broadly.

---

## Debugging Auth Silent Failures

### Symptom: Sign-in succeeds, cookie is set, but dashboard flashes and redirects to `/signin`

**Root cause chain:**
1. Layout component (often `(app)/layout.tsx` or a `Providers` wrapper) runs `useEffect` that checks `localStorage` for an auth token
2. NextAuth v5 uses HTTP cookies (`__Secure-authjs.session-token`), not `localStorage`
3. The layout sees no token → `router.replace("/signin")`

**Fix:** Replace localStorage checks with `useSession()` from `next-auth/react`:
```tsx
import { useSession } from "next-auth/react";

const { data: session, status } = useSession();
useEffect(() => {
  if (status === "unauthenticated") {
    router.replace("/signin");
  }
}, [status, router]);
```

**Also:** Wrap the root layout with `SessionProvider`:
```tsx
// app/providers.tsx
"use client";
import { SessionProvider } from "next-auth/react";
export default function Providers({ children }) {
  return <SessionProvider>{children}</SessionProvider>;
}
```

Without `SessionProvider`, `useSession()` won't receive updates from the cookie-based session.

### Refresh button / React context not working

**Root cause:** `Providers` component had only `SessionProvider` — missing `RefreshProvider`. Since context providers must be ancestors of consumers, `useRefresh()` got the default context value instead.

**Fix:** Include both in the same Providers component:
```tsx
import { SessionProvider } from "next-auth/react";
import { RefreshProvider } from "@/lib/context/RefreshContext";

export default function Providers({ children }) {
  return (
    <SessionProvider>
      <RefreshProvider>{children}</RefreshProvider>
    </SessionProvider>
  );
}
```

---

## Neon Auth (`@neondatabase/auth`)

Neon Auth provides managed authentication via the `@neondatabase/auth` package. It wraps Better Auth and exposes a clean API for email/password, OAuth (Google), and session management.

### Key files to create/modify:
- `lib/neon-auth.ts` — Neon Auth client singleton
- `lib/auth/session.ts` — Session verification, `getSessionUser()`, JWT helpers
- `app/(login)/actions.ts` — Server actions for signIn, signUp, signOut, etc.
- `app/auth/callback/route.ts` — OAuth callback handler

### Beta package type issues

`@neondatabase/auth@0.3.0-beta` has incomplete types — methods like `signIn.email()` return union types where `.user` doesn't exist on the type. **Always cast with `(fn as Function)(args) as any`** when accessing the result:

```typescript
const session = await (neonAuth.signIn.email as Function)({ email, password }) as any;
const neonUserId = session.user?.id;
```

### Server Actions Pattern

Neon Auth returns objects wrapped in a result type. Always cast:

```typescript
// signIn
const session = await (neonAuth.signIn.email as Function)({ email, password }) as any;

// signUp
const session = await (neonAuth.signUp.email as Function)({ email, password, name }) as any;

// signOut
await neonAuth.signOut();

// OAuth
const result = await (neonAuth.signIn.social as Function)({
  provider: 'google',
  callbackURL: '/dashboard',
}) as any;
```

### Dashboard Auth Protection

The dashboard layout must be dynamic (not statically generated):
```typescript
export const dynamic = 'force-dynamic';

export default async function DashboardLayout({ children }) {
  const user = await getUser();
  if (!user) redirect('/sign-in');
  return <DashboardShell user={user}>{children}</DashboardShell>;
}
```

### `AUTH_SECRET` MUST match Neon Auth signing key

The JWT is signed with HS256 using the `AUTH_SECRET` env var. If it doesn't match what's configured in Neon Auth, session verification fails silently.

### `BetterAuthVanillaAdapter` cannot be imported

The adapter is the default — `createAuthClient(url)` uses it automatically without being passed. The `@neondatabase/auth/vanilla/adapters` subpath exports the type but NOT the runtime value for direct import.

---

## See Also
- `fastify-to-nextjs-api-migration` — for NextAuth v5 migration from Fastify/JWT auth (Edge middleware, route handlers, build verification)
- `third-party-api-integration` — for the broader server-side client and credential storage patterns