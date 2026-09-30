# 502 Bad Gateway from large auth cookies (nginx proxy buffer overflow)

Verified 2026-09-14 on AMA (`server.example.com:3200` → docker `127.0.0.1:3210`).
Reusable for ANY Supabase/NextAuth/Clerk app proxied by nginx.

## Symptom

User reports **502 Bad Gateway / nginx/1.24.0 (Ubuntu)** on the live link. The
container is healthy, `docker compose ps` shows `Up (healthy)`, and your own
`curl` against the same URL returns **200**. It looks transient or
user-environment-only. It is neither.

Browser-dependent: the user saw it in **Brave but not Safari**. That asymmetry
is the tell — Brave's cookie jar is larger, so it crosses the buffer limit
while Safari's stays under it.

## Root cause

nginx's **response**-header buffer (`proxy_buffer_size`) defaults to **4 KB**.
Supabase chunked auth cookies (`sb-<ref>-auth-token.0`, `.1`, …) are JWTs, and
the app's `Set-Cookie` response headers can exceed 4 KB. nginx then refuses the
upstream response:

```
upstream sent too big header while reading response header from upstream,
client: <ip>, server: <host>,
request: "GET /chat HTTP/2.0", upstream: "http://127.0.0.1:3210/chat"
```

Measured here: 2 cookies, **5,231 bytes** of cookie header
(`sb-api-auth-token.0` = 3,180, `sb-api-auth-token.1` = 2,009).

**Why curl lies to you**: curl sends no cookies, so the upstream response has
small headers and the check passes every time. A cookie-less health check
CANNOT detect this class of failure. Reproduce with a real browser session, or
forge a large `Cookie:` header.

## Fix

Two families of directive. **Context matters — getting this wrong fails
`nginx -t` and leaves an invalid config on disk:**

| Directive | Valid context |
|---|---|
| `proxy_buffer_size`, `proxy_buffers`, `proxy_busy_buffers_size` | `http`, `server`, `location` |
| `client_header_buffer_size`, `large_client_header_buffers` | `http`, `server` only — **NOT `location`** |

```
upstream sent too big header      → proxy_buffer_size / proxy_buffers
request header too large (400)    → client_header_buffer_size / large_client_header_buffers
```

Working vhost fragment (request-buffer directives at server level, response
buffers in the location):

```nginx
server {
    listen 3200 ssl http2;
    server_name         server.example.com;
    ssl_certificate     /etc/ssl/nginx/server.example.com-cert.pem;
    ssl_certificate_key /etc/ssl/nginx/server.example.com-key.pem;
    include ssl.conf;

    # request-side buffers — server level only
    client_header_buffer_size   32k;
    large_client_header_buffers 4 32k;

    location / {
        proxy_pass http://127.0.0.1:3210;
        proxy_set_header Host $host:$server_port;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 300s;

        # response-side buffers — auth Set-Cookie headers exceed the 4k default
        proxy_buffer_size       32k;
        proxy_buffers           8 32k;
        proxy_busy_buffers_size 64k;
    }
}
```

The exact failure when mis-nested:

```
[emerg] "client_header_buffer_size" directive is not allowed here in
/etc/nginx/sites-enabled/<site>:32
```

## Deploy sequence (shared box — never edit in place over SSH heredocs)

1. Write the new vhost locally to `/tmp/<site>-nginx.conf`.
2. `scp` it up, `sudo cp` into `sites-available/`.
3. **`sudo nginx -t`** — MUST pass before reload. If it fails, the invalid file
   is already on disk; fix and re-test immediately rather than moving on.
4. `sudo systemctl reload nginx` (reload, not restart — other vhosts on the box
   keep serving).
5. Confirm `systemctl is-active nginx` and that the app URL still returns 200.

## Verification that actually proves it

Cookie-less curl is worthless here. Do all of:

1. **Forge a large cookie header** (~5.6 KB) and hit `/`, `/login`, `/chat`:
   ```bash
   BIG=$(python3 -c "
   chunk = 'base64urlpayloadsegment' * 60
   print('; '.join('sb-api-auth-token.%d=%s' % (i, chunk) for i in range(4)))
   ")
   curl -sk -o /dev/null -w "%{http_code}" -H "Cookie: $BIG" "https://HOST/chat"
   ```
   Expect 307/200 — never 502.
2. **Real browser login**, print the cookie sizes, then hammer the routes and
   reload several times asserting no 4xx/5xx:
   ```python
   cookies = await ctx.cookies()
   print("approx header bytes:", sum(len(c["name"]) + len(c["value"]) + 2 for c in cookies))
   codes = []
   page.on("response", lambda r: codes.append((r.status, r.url)) if r.status >= 400 else None)
   for _ in range(3):
       print((await page.reload()).status)   # expect 200 each
   ```
3. **Error-log timeline check** — prove no NEW 502s after the reload, don't
   just assert none ever existed:
   ```bash
   sudo grep " 502 " /var/log/nginx/access.log | tail -5
   sudo grep -c " 502 " /var/log/nginx/access.log   # compare count + timestamps
   sudo tail -3 /var/log/nginx/error.log
   ```
   The pre-existing 502s keep the count non-zero forever; compare timestamps
   against the reload time. Also grep the access log's **user-agent** field —
   the browser asymmetry (Brave vs Safari) shows up right there and confirms
   the cookie-size theory.

## Pitfalls

- Do NOT conclude "transient, container is fine" from `docker compose ps` +
  a passing cookie-less curl. That combination is exactly what this bug looks
  like. Read `nginx/error.log` before dismissing a 502.
- An nginx 502 with a *healthy* upstream is almost always a buffer/timeout
  mismatch, not a dead app.
- This fix lives on the server, NOT in the repo — there is nothing to commit.
  Say so explicitly so the user isn't left wondering where the change went.
- Bumping buffers is a mitigation, not a cure: if the app can shrink its
  session cookie (or move the session server-side), that is the real fix.
