"""
LOCAL PROXY SERVER for Indiana CD-9 Democratic Targeting Guide
---------------------------------------------------------------
Routes Anthropic API calls from the browser through this server,
avoiding CORS restrictions on direct browser-to-API requests.

USAGE:
  1. Edit API_KEY below with your Anthropic API key
  2. Run:  python proxy.py        (Python 3 — no extra packages needed)
  3. Open the .html file in your browser
  4. The page will automatically use http://localhost:3000
"""

import http.server, urllib.request, json, os

# ── Set your Anthropic API key here ──────────────────────────────────────────
API_KEY = "sk-ant-YOUR-KEY-HERE"
# ─────────────────────────────────────────────────────────────────────────────

PORT = 3000


class ProxyHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  [{self.address_string()}] {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data    = body,
            method  = "POST",
            headers = {
                "Content-Type":      "application/json",
                "x-api-key":         API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data   = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            data   = e.read()
            status = e.code

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors()
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print()
    print("  Indiana CD-9 Targeting Guide — Local Proxy")
    print("  ──────────────────────────────────────────")
    print(f"  Proxy running at: http://localhost:{PORT}")
    print("  Open the .html file in your browser.")
    print("  Press Ctrl+C to stop.")
    print()
    server = http.server.HTTPServer(("127.0.0.1", PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Proxy stopped.")
