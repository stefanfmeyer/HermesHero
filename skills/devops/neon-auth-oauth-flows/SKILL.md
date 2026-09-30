---
name: neon-auth-oauth-flows
description: >
  Working Google OAuth sign-in/sign-up architecture for Neon Auth (Better Auth)
  in Next.js App Router projects. The naive server-action pattern silently
  fails; this covers the @neondatabase/auth/next/server SDK flow — API proxy,
  middleware verifier exchange, callback JWT minting — plus the pitfalls that
  cost a full debugging session (verifier landing on site root, relative
  callbackURL, urlencoded form POST, challenge cookie expiry).
trigger: Setting up or debugging Google/social OAuth with Neon Auth (@neondatabase/auth), fixing "Google sign-in failed" or OAuth callbacks that never establish a session, wiring OAuth buttons in Next.js 16, or integrating BYO AI provider keys into a SaaS.
tags: [neon, neon-auth, oauth, google, better-auth, nextjs, app-router, session, jwt, byo-ai-keys]
---

# Neon Auth OAuth Flows (Next.js App Router)

## Why the server-action pattern fails

Calling `neonAuth.signIn.social({provider, callbackURL})` from a server action
starts the OAuth flow, but the OAuth handshake cookies (challenge etc.) are set
by the Neon auth server on ITS domain — never on your app's domain. When Google
returns, your callback route has no session and every sign-in fails with a
generic error. There is no error at setup time; the flow only breaks at the end.

## Working architecture (verified on production, 2026-09-12)

Four pieces, using `@neondatabase/auth/next/server` (ships inside
`@neondatabase/auth`, subpath `./next/server`):

### 1. Server SDK instance (`lib/neon-auth-server.ts`)

```typescript
import { createNeonAuth } from '@neondatabase/auth/next/server';

export const neonAuthServer = createNeonAuth({
  baseUrl: process.env.NEON_AUTH_URL, // e.g. https://ep-xxx.neonauth.eu-west-2.aws.neon.tech/neondb/auth
  cookies: {
    secret: process.env.NEON_AUTH_COOKIE_SECRET || process.env.AUTH_SECRET || '',
  },
});
```

The `createNeonAuth` config does NOT accept `logLevel` (type error if passed).

### 2. API proxy route (`app/api/auth/[...all]/route.ts`)

```typescript
const handlers = neonAuthServer.handler();

export async function GET(request: NextRequest, ctx: { params: Promise<any> }) {
  const { all } = await ctx.params;
  return handlers.GET(request as any, { params: Promise.resolve({ path: all ?? [] }) });
}
export async function POST(request: NextRequest, ctx: { params: Promise<any> }) {
  const { all } = await ctx.params;
  return handlers.POST(request as any, { params: Promise.resolve({ path: all ?? [] }) });
}
```

Purpose: the browser starts Google sign-in on YOUR domain, so Neon's
Set-Cookie challenge cookies land on your domain. Two type gotchas:
- Next.js 16 catch-all segments deliver `params.all`; the SDK handler expects
  `ctx.params.path`. You MUST translate (above) or the proxy 500s with
  `Cannot read properties of undefined (reading 'join')`.
- Do NOT re-export `export const { GET, POST } = neonAuthServer.handler()` —
  Next.js route type-checks reject the SDK's `(Request, {params})` signature.

### 3. Middleware / proxy: verifier exchange

When Google completes, Neon redirects the browser to your callbackURL with
`?neon_auth_session_verifier=...` appended. The SDK middleware
(`neonAuthServer.middleware({ loginUrl: '/' })`) detects the verifier plus the
`__Secure-neon-auth.session_challange` cookie, exchanges them upstream, and
returns a redirect carrying the Neon session cookies on your domain.

`loginUrl: '/'` disables the SDK's route protection (you keep your own), while
the OAuth exchange still runs. Wrap it in try/catch and fall back to
`NextResponse.next()` on error so a Neon outage never breaks the site.

**Critical pitfall:** after a successful exchange the SDK redirects to the
pre-exchange URL minus the verifier. If Neon redirected to your site ROOT
rather than your callback, the user lands on the homepage signed in to Neon
but with NO app session. Fix in middleware:

```typescript
if (sdkResponse.headers.get('location')) {
  const target = new URL(sdkResponse.headers.get('location')!);
  if (target.pathname !== '/auth/callback') {
    const callbackUrl = new URL('/auth/callback', request.url);
    callbackUrl.searchParams.set('redirect', target.pathname + (target.search || ''));
    const cbRes = NextResponse.redirect(callbackUrl);
    for (const c of sdkResponse.headers.getSetCookie()) {
      cbRes.headers.append('set-cookie', c);
    }
    return cbRes;
  }
  return sdkResponse;
}
```

### 4. Callback route (`app/auth/callback/route.ts`)

Reads the session via `neonAuthServer.getSession()`, then:
- No session → redirect to `/sign-in?error=...` (log arriving cookie names first — see diagnostics below)
- Session + no local user → create local `users` row (with `neonUserId`, empty passwordHash for OAuth) AND provision a team + teamMembership, exactly like email sign-up does
- Session + existing user → sync name if changed
- Mint the app's own session JWT (httpOnly cookie) and redirect to the `redirect` param (default `/dashboard`)

Keeping a first-class app JWT (not proxying Neon's opaque session) lets
middleware roll it on GET and lets `getUser()` resolve the local row by
neonUserId without a per-request Neon network call.

### 5. The Google button (client component)

```tsx
fetch('/api/auth/sign-in/social', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    provider: 'google',
    callbackURL: `${window.location.origin}/auth/callback?redirect=${encodeURIComponent(redirect || '/dashboard')}`,
  }),
})
  .then(res => res.json())
  .then(data => { window.location.href = data?.url ?? '/sign-in?error=Google+sign-in+failed'; });
```

Three requirements:
- **JSON body** — an HTML form POST sends urlencoded and the proxy rejects it
- **ABSOLUTE callbackURL** — a relative one can be resolved against the Neon
  auth domain instead of your app
- **Follow `data.url`** — the response is `{url, redirect:true}`, not a redirect itself

## Diagnostics

- **Callback has no session:** log `request.headers.get('cookie')` names. If
  the `__Secure-neon-auth.session_token` cookie is missing, the verifier
  exchange failed (bad verifier, expired challenge cookie, or the exchange
  never ran because middleware didn't see the verifier param).
- **Proxy 500 `reading 'join'`:** catch-all params not translated (`all` → `path`).
- **Bad verifier:** the exchange returns null and the SDK falls through to
  'allow' — the original page renders (200) with no session. Graceful, but
  silent; check logs.
- **Challenge cookie expiry:** Neon sets `session_challange` with Max-Age=600.
  A user who waits >10 min on the Google consent screen will fail the exchange.
- **Bogus code/state tests:** `GET <authUrl>/callback/google?code=bogus&state=bogus`
  returns 302 to `<authUrl>/error?error=state_mismatch` — useful to confirm the
  Neon OAuth route exists (`/callback/google`, NOT `/oauth/callback/...`).

## Testing the flow

You cannot complete a real Google consent from a sandboxed environment (DNS to
accounts.google.com is often blocked). What you CAN verify end to end:

1. `POST /api/auth/sign-in/social` with JSON `{provider:'google', callbackURL:'https://<domain>/auth/callback?redirect=/dashboard'}` → 200 with `{url}` + `set-cookie` challenge cookies on your domain
2. Follow the returned init URL → 302 to `accounts.google.com/o/oauth2/v2/auth?...&client_id=<neon-shared-client>` proves the OAuth handoff is live
3. Hit `<origin>/auth/callback?...&neon_auth_session_verifier=fake` with a dummy challenge cookie → should land on sign-in with error (invalid verifier rejected), proving the middleware exchange path executes

The final consent leg needs a human with a real Google account. Ship it, then
have the user test sign-up (new account) AND sign-in (same account).

## Companion: BYO AI provider keys

When the product policy is "users bring their own AI key" (no platform AI
usage in plans): store `aiProvider` + `aiApiKey` per user row, expose a
Settings card with provider dropdown + key input, and **live-validate the key
with a tiny probe request before saving** (1-token chat completion; Anthropic
needs `x-api-key` + `anthropic-version` headers, the rest use Bearer).
Normalize providers behind one `callChat(userId, {system, prompt, jsonMode})`
that picks the endpoint per provider: OpenAI-compatible (`/v1/chat/completions`
with Bearer) for openai/openrouter/deepseek/mistral; Anthropic uses
`/v1/messages` with `max_tokens` and a different header scheme. When no key is
set, throw a typed `AiKeyMissingError` the UI turns into
"No AI provider configured. Add your AI provider and API key in Settings > General".