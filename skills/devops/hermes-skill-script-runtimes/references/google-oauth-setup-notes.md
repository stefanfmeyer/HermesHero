# Google OAuth Setup via google-workspace skill (session notes 2026-09-02)

Session-specific quirks hit while authorizing you@example.com on the workstation.

## Installed setup.py vs SKILL.md mismatch

The installed `setup.py` (google-workspace skill) does NOT accept
`--services` or `--format` on `--auth-url`, despite SKILL.md documenting:

```
$GSETUP --auth-url --services email,calendar --format json
```

Actual behavior: `setup.py --auth-url` alone prints the auth URL (all
scopes: gmail.readonly/send/modify, calendar, drive, documents,
contacts.readonly, spreadsheets). No service selection is supported by
the installed script. Plain URL text, not JSON.

Runtime used: `~/.hermes/gws-venv/bin/python` (see parent SKILL.md).

## Auth URL flow quirks

- Redirect URI is `http://localhost:1`. After the user clicks
  Allow/Continue, the browser tab spins forever ("loads infinitely")
  because nothing listens on localhost:1. **This is expected success
  behavior, not failure** — tell the user up front.
- The auth code lives in the browser ADDRESS BAR
  (`http://localhost:1/?code=4/0A...&scope=...`). The user must copy the
  whole URL and paste it back; the page itself never renders content.
- A pending PKCE session (`state` + `code_verifier`) is stored at
  `~/.hermes/google_oauth_pending.json`. Generating a new `--auth-url`
  OVERWRITES it — any URL sent before regeneration is dead, and the
  user's "select all and continue then infinite load" attempt against a
  stale session may produce an auth-code that fails exchange. If exchange
  fails with expired/used code, the script returns a `fresh_auth_url`
  — send that immediately.
- User report: consent screen (checkboxes + Continue) worked in both
  normal and incognito windows but tab hung after Continue — consistent
  with the expected localhost:1 hang. Diagnose by asking what the
  address bar shows, not by assuming failure.

## Google Cloud console checklist (gmail.com accounts)

- OAuth client type must be "Desktop app"
- If app is in Testing mode: gmail.com test users are rejected for
  Desktop apps. Fix: console.cloud.google.com/auth/audience → publish
  app to Production. Then `Error 403: access_denied` disappears.
- Enable APIs: Gmail, Calendar, Drive, Docs, People, Sheets

## Token/credential locations

- `~/.hermes/google_client_secret.json` (from `--client-secret PATH`;
  pasting the raw JSON content to a file and passing that path also works)
- `~/.hermes/google_token.json` (auto-refreshing, created by
  `--auth-code` exchange)