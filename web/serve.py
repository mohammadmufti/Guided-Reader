#!/usr/bin/env python3
"""
Static server with SPA history fallback.

    python web/serve.py [dist_dir] [port] [base_path]

`python -m http.server` has no fallback, so a deep link like /hadith/42 returns
its own 404 page and the app never boots — which makes every deep-link test in
the e2e suites fail for a reason that has nothing to do with the app. Used by
CI and available locally for the same reason.

`base_path` mirrors the BASE_PATH the app was built with. GitHub Pages serves
the site under /<repo>/, so CI builds with that prefix — and a server that
does not strip it answers the app's own JS request with index.html (the SPA
fallback), text/html where the browser expected a script, and nothing ever
renders. That is precisely how the first CI runs of the gates failed. Defaults
to "/", which leaves local root-build behaviour untouched.

Real hosts do this differently: GitHub Pages via a 404.html copy, Netlify and
Cloudflare via a redirect rule. This exists so the tests can run against the
built output without a host.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "dist")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5173
BASE = (sys.argv[3] if len(sys.argv) > 3 else "/").strip() or "/"
if not BASE.startswith("/"):
    BASE = "/" + BASE
if not BASE.endswith("/"):
    BASE += "/"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def send_head(self):
        raw = self.path.split("?")[0]
        # Strip the build-time base path, the way the real host's routing
        # would place the site at that prefix.
        if BASE != "/":
            if raw == BASE.rstrip("/"):
                # GitHub Pages 301s the slashless directory URL to the
                # trailing-slash form; without that, the router's basename
                # never strips and the root redirect does not fire.
                self.send_response(301)
                self.send_header("Location", BASE)
                self.end_headers()
                return None
            if raw == BASE:
                raw = "/"
            elif raw.startswith(BASE):
                raw = "/" + raw[len(BASE):]
            self.path = raw + ("?" + self.path.split("?", 1)[1] if "?" in self.path else "")
        path = self.translate_path(raw)
        # Anything that is not a real file and not an asset request is a client
        # route: hand back the shell and let the router deal with it.
        if not os.path.exists(path) and not raw.startswith(("/assets", "/data")):
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    print(f"serving {ROOT} on http://127.0.0.1:{PORT}{BASE} (SPA fallback on)")
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as srv:
        srv.serve_forever()
