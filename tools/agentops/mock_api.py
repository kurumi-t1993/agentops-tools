#!/usr/bin/env python3
"""mock_api.py

Offline-first mock API server generator.

Starts a local HTTP server (127.0.0.1) serving:
- /health
- /v1/items (GET)
- /v1/items/<id> (GET)

Data comes from a JSON file, or generated synthetic data.

Usage:
  python3 mock_api.py --port 8089 --count 50
  python3 mock_api.py --data data.json

This is meant to let us build integrations without touching real external APIs.

No deps.
"""

from __future__ import annotations

import argparse
import json
import random
import socketserver
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler
from typing import Dict, List, Optional


@dataclass
class Item:
    id: str
    name: str
    status: str
    tags: List[str]


def gen_items(n: int, seed: int = 0) -> List[Item]:
    rnd = random.Random(seed)
    statuses = ["new", "active", "archived"]
    tags = ["alpha", "beta", "gamma", "jp", "us", "ops"]
    items: List[Item] = []
    for i in range(1, n + 1):
        items.append(
            Item(
                id=str(i),
                name=f"Item {i}",
                status=rnd.choice(statuses),
                tags=rnd.sample(tags, k=rnd.randint(0, 3)),
            )
        )
    return items


def load_items(path: str) -> List[Item]:
    data = json.load(open(path, "r", encoding="utf-8"))
    items: List[Item] = []
    for obj in data.get("items", []):
        items.append(Item(id=str(obj.get("id")), name=str(obj.get("name")), status=str(obj.get("status")), tags=list(obj.get("tags") or [])))
    return items


class Handler(BaseHTTPRequestHandler):
    items: Dict[str, Item] = {}

    def _send(self, code: int, obj: dict):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # quiet by default
        return

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._send(200, {"ok": True})
        if path == "/v1/items":
            return self._send(200, {"items": [asdict(v) for v in self.items.values()]})
        if path.startswith("/v1/items/"):
            _id = path.split("/v1/items/", 1)[1]
            it = self.items.get(_id)
            if not it:
                return self._send(404, {"error": "not_found"})
            return self._send(200, {"item": asdict(it)})
        return self._send(404, {"error": "not_found"})


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run a local mock API server.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8089)
    ap.add_argument("--data", default=None, help="JSON file with {items:[...]}.")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    if args.data:
        items = load_items(args.data)
    else:
        items = gen_items(args.count, seed=args.seed)

    Handler.items = {it.id: it for it in items}

    with socketserver.TCPServer((args.host, args.port), Handler) as httpd:
        print(f"mock_api listening on http://{args.host}:{args.port}")
        httpd.serve_forever()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
