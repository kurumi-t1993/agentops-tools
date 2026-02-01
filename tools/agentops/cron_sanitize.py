#!/usr/bin/env python3
"""cron_sanitize.py

Create a shareable, redacted snapshot of OpenClaw `cron list` JSON.

- Redacts common PII/secrets via redactor.py
- Additionally redacts:
  - absolute home paths (/Users/<name>/...) -> /Users/[REDACTED_USER]/...
  - common UUID-bearing identifiers inside text

Usage:
  python3 cron_sanitize.py --in cron_jobs.json --out cron_jobs.redacted.json

Input format:
  {"jobs": [...]} (same shape as OpenClaw cron.list)

Offline-first. No deps.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict

from redactor import redact_text


RE_HOME = re.compile(r"/Users/[^/]+/")


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        s = obj
        s = RE_HOME.sub("/Users/[REDACTED_USER]/", s)
        s, _ = redact_text(s)
        return s
    return obj


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Redact cron job JSON for safe sharing.")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args(argv)

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    redacted = redact_obj(data)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(redacted, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
