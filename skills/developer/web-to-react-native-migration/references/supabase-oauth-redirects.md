# Supabase OAuth redirects for a native/RN-web client

Captured 2026-09-18 while answering *"what do I add to supabase auth for google
OAuth to ensure it redirects to login for AMA?"*

## The answer, and where each piece lives

| Setting | Value | Why |
|---|---|---|
| Supabase → Auth → URL Configuration → **Redirect URLs** | `the company-ama://auth-callback` | the exact string the client sends |
| Supabase → Auth → URL Configuration → **Site URL** | `https://<app-host>:<port>/login` | the fallback when a redirect fails validation |
| Google Cloud console → Authorized redirect URIs | `https://<supabase-host>/auth/v1/callback` | Supabase's own callback — **no per-app value** |

The app's value comes from two places, both in the repo:

```
app.json            "scheme": "the company-ama"
app/lib/oauth.ts    return `${APP_SCHEME}://auth-callback`;
```

Read them rather than guessing — `redirectUri()` branches per platform, and the
web branch returns something completely different (`${origin}/auth/callback`),
which is where the second trap below lives.

## Why "it redirects to the wrong place" means the allowlist is missing

Supabase does **not** raise an error when `redirectTo` is not matched. It falls
back to **Site URL**. So the user story is:

> "Google sign-in completes fine, then it dumps me on the platform login / the
> main app instead of AMA."

That is the missing-allowlist symptom, not a broken OAuth client. Corollary: set
Site URL to something sensible for the app (its own `/login`), because you cannot
stop Supabase from using it as the fallback.

## Glob rules, if you decide to wildcard

Separators are `.` and `/`. Asymmetric and easy to get wrong:

| Pattern | Matches | Does NOT match |
|---|---|---|
| `the company-ama://*` | `the company-ama://auth-callback` | `the company-ama://a/b` |
| `the company-ama://**` | `the company-ama://a/b` and anything else | — |
| `the company-ama://?` | `the company-ama://a` (single char) | `the company-ama://ab` |

Note `the company-ama://*` would **also** match `the company-ama://evil-callback`.
When the client sends one hardcoded string, there is no reason to wildcard — add
the exact URL.

## Confirming the Google console side needs nothing app-specific

Decode the authorize call and read the `redirect_uri` it emits:

```bash
SUPA=https://api.example.com
ANON=$(grep -E "^EXPO_PUBLIC_SUPABASE_ANON_KEY=" .env | cut -d= -f2- | tr -d '"'"'"' \r')

for R in "the company-ama://auth-callback" \
         "https://<app-host>:<port>/auth/callback" \
         "https://evil.example.com/steal"; do
  ENC=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$R")
  LOC=$(curl -s -D - -o /dev/null "$SUPA/auth/v1/authorize?provider=google&redirect_to=$ENC" \
        -H "apikey: $ANON" | grep -i '^location:' | head -1 | sed 's/^[Ll]ocation: //' | tr -d '\r')
  echo "requested: $R"
  python3 - "$LOC" <<'PY'
import sys, urllib.parse as u
q = u.parse_qs(u.urlparse(sys.argv[1]).query)
for k in ("redirect_uri", "client_id", "scope"):
    if k in q: print(f"   {k}={q[k][0][:110]}")
PY
done
```

Observed output — **identical for every requested value**, including a hostile
one:

```
redirect_uri=https://api.example.com/auth/v1/callback
client_id=134574856885-...apps.googleusercontent.com
scope=email profile
```

Two conclusions:

1. The provider-side redirect is Supabase's fixed callback. The Google console
   entry is `https://<supabase-host>/auth/v1/callback` for every app on that
   project — **do not send the user to the console to add a deep link.**
2. The allowlist is **not** enforced at this endpoint: a hostile `redirect_to`
   still 302s to Google. Do not use this probe to test allowlist membership — it
   only proves the provider is wired up. (Enforcement happens on the way back,
   and its failure mode is the silent Site-URL fallback above.)

`provider=google` returning a 302 to `accounts.google.com` with a real
`client_id` does confirm the provider is enabled. Cross-check:

```bash
curl -s "$SUPA/auth/v1/settings" -H "apikey: $ANON" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['external']['google'])"   # -> True
```

## What you CANNOT verify with the anon key — say so

`/auth/v1/settings` returns only: `disable_signup`, `external`,
`mailer_autoconfirm`, `passkeys_enabled`, `phone_autoconfirm`, `saml_enabled`,
`saml_private_key_next_configured`, `sms_provider`.

Verified absent: `site_url`, `uri_allow_list`, `additional_redirect_urls`,
`redirect_urls`, `external_redirect_urls`.

So a request phrased "ensure it redirects to login" **cannot** be answered by
reading the current config — the allowlist is dashboard-only (or Management API
with a personal access token, which is a different credential from the anon key).
State what to add, and state explicitly that the current contents are
unverifiable from this key rather than implying you checked.

## The web twin: a redirect target that is not a route

`redirectUri()` on web returns `${origin}/auth/callback`, but the Expo Router app
(`app/` directory) had only `_layout.tsx`, `index.tsx`, `login.tsx`, `chat.tsx`.
Loading that URL produced:

```
Unmatched Route
Page could not be found.
```

…while the HTTP status was **200**, because `output: "single"` (or any SPA
fallback) serves `index.html` for unmatched paths.

### Probe that actually detects it

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<app>/auth/callback   # 200  <- useless
```

```python
# renders the truth
await page.goto(f"{APP}/auth/callback?code=fake-test-code")
body = await page.inner_text("body")
print("Unmatched Route" in body)     # True == the route does not exist
```

Also check the filesystem for the route file — Expo Router is file-based, so a
route that does not exist as a file does not exist:

```bash
find app -name "*.tsx" | sort      # compare against every redirect target you allowlist
```

### Why it matters

Allowlisting `https://<app>/auth/callback` in Supabase would be adding a URL that
dead-ends — the user completes Google, gets redirected, and lands on a 404 that
reports as 200. Either create the route (it must also handle the PKCE `code`
exchange, since `detectSessionInUrl` is `true` on web) or point the web branch at
a route that exists (`/login`).

## Checklist

1. Read the client's redirect value from `app.json` scheme + the OAuth module.
2. Add it **exactly** to Supabase → Auth → URL Configuration → Redirect URLs.
3. Set Site URL to the app's own login, not the custom scheme.
4. Confirm the provider's redirect is Supabase's callback — do not touch the
   Google console for per-app values.
5. Prove every allowlisted target is a real route by rendering it, not by
   status code.
6. State that the existing allowlist contents are unverifiable from the anon key.
