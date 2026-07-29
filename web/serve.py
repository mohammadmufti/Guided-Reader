#!/usr/bin/env python3
"""
Static server with SPA history fallback.

    python web/serve.py [dist_dir] [port]

`python -m http.server` has no fallback, so a deep link like /hadith/42 returns
its own 404 page and the app never boots — which makes every deep-link test in
the e2e suites fail for a reason that has nothing to do with the app. Used by
CI and available locally for the same reason.

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


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def send_head(self):
        path = self.translate_path(self.path.split("?")[0])
        # Anything that is not a real file and not an asset request is a client
        # route: hand back the shell and let the router deal with it.
        if not os.path.exists(path) and not self.path.startswith(("/assets", "/data")):
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    print(f"serving {ROOT} on http://127.0.0.1:{PORT} (SPA fallback on)")
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as srv:
        srv.serve_forever()
