#!/usr/bin/env python3
"""agentops_suite.py

Glue script to run the AgentOps safety checks in a repeatable way.

What it does (local-only):
- Run unit tests
- Run secrets scan against tracked files
- Optionally run commands under network_airlock
- Generate a receipt

This is a convenience tool for "ship discipline".
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional


def sh(cmd: List[str]) -> int:
    p = subprocess.run(cmd)
    return int(p.returncode)


def bash(cmd: str) -> int:
    return sh(["/bin/bash", "-lc", cmd])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run AgentOps checks and generate a receipt.")
    ap.add_argument("--repo", default="/Users/day/.openclaw/workspace")
    ap.add_argument("--airlock", action="store_true", help="Run tests under network_airlock.")
    ap.add_argument("--receipt", default=None, help="Receipt output path (md).")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    if not repo.exists():
        raise SystemExit("repo not found")

    rc = 0

    if args.airlock:
        rc |= bash(f"cd {repo} && python3 tools/agentops/network_airlock.py -- python3 -m unittest -q")
    else:
        rc |= bash(f"cd {repo} && python3 -m unittest -q")

    # secrets scan tracked
    rc |= bash(f"cd {repo} && python3 tools/agentops/secrets_scan.py --fail")

    if args.receipt:
        rc |= bash(f"cd {repo} && python3 tools/agentops/receipts_builder.py --out {args.receipt} --cmd 'python3 -m unittest -q'")

    return 0 if rc == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
