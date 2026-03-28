#!/usr/bin/env python3
"""Minimal JSON API server for Docker Compose demo."""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({"message": "Hello from Edge Computing!"})
        self.wfile.write(body.encode())


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("Server running on http://0.0.0.0:5000")
    server.serve_forever()
