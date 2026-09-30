#!/usr/bin/env python3
"""Serve a static SPA export with a fallback so deep routes resolve.

Why this exists
---------------
An Expo/Next/Vite web export writes ONE `index.html` plus a JS bundle. The app's
router resolves `/chartlab`, `/dashboard/ads`, etc. on the CLIENT, but a plain
`python3 -m http.server` returns **404 for every path that has no matching file**.
The symptom is maddening: the route "doesn't exist", the page is blank, and you
start debugging the app instead of the server.

Two consequences that both cost real time:

1. **The route must fall back to index.html.** That is what this script does.
2. **A 200 from a fallback server proves NOTHING about the route.**
   `/dashboard/creatives/<id>/edit` returns 200 and renders an empty shell
   because the fallback serves index.html for it too. Never use a status code to
   decide a route works — load it and assert the destination RENDERED.

Also beware the served-directory trap: editing this file's DIR (e.g. with `sed`)
does NOT affect an already-running process. Kill it and relaunch, then confirm the
new build is the one being served (check for a string unique to your change)
before trusting any measurement — otherwise you silently test the PREVIOUS build,
which reads as "my assertion doesn't catch the bug".

Usage
-----
    /tmp/pw-venv/bin/python spa_fallback_server.py --dir /tmp/my-export --port 4599

Run it as a background process, then poll it before the test batch:

    curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:4599/
    curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:4599/<deep-route>

The asset path still must resolve exactly — only MISSING paths fall back, so the
JS bundle is served normally and the client router takes over.
"""

import argparse
import http.server
import os
import socketserver
import sys


def make_handler(directory: str):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)

        def do_GET(self):  # noqa: N802 - stdlib naming
            path = self.path.split("?")[0]
            fs = os.path.join(directory, path.lstrip("/"))
            # A real file (or the root) is served as-is; anything else is a
            # client-side route, so hand back index.html and let the router run.
            if path != "/" and not os.path.exists(fs):
                self.path = "/index.html"
            return super().do_GET()

        def log_message(self, *a):
            # Quiet by default: the request log buries the probe output.
            pass

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, help="export directory to serve")
    ap.add_argument("--port", type=int, default=4599)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print(f"not a directory: {args.dir}", file=sys.stderr)
        return 1

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), make_handler(args.dir)) as httpd:
        print(f"serving {args.dir} on http://{args.host}:{args.port}", flush=True)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
