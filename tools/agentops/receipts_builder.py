#!/usr/bin/env python3
"""receipts_builder.py

Generate a lightweight "receipt" for a change:
- repo status
- latest commit
- diffstat
- optional command outputs (e.g., tests)

This is meant for local proof-of-work and reproducibility.

Usage:
  python3 receipts_builder.py --out receipts/2026-02-01.md --cmd "python3 -m unittest -q"

Offline-first. No deps.
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def sh(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)


def try_sh(cmd: List[str]) -> str:
    try:
        return sh(cmd)
    except subprocess.CalledProcessError as e:
        return e.output + f"\n[command exited {e.returncode}]\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a repo receipt (markdown).")
    ap.add_argument("--out", required=True, help="Output markdown path.")
    ap.add_argument("--cmd", action="append", default=[], help="Command to run and capture (repeatable).")
    args = ap.parse_args(argv)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone().isoformat(timespec="seconds")

    parts: List[str] = []
    parts.append(f"# Receipt ({now})\n")

    parts.append("## Repo\n")
    parts.append("```\n" + try_sh(["git", "rev-parse", "--show-toplevel"]).strip() + "\n```\n")

    parts.append("## Status\n")
    parts.append("```\n" + try_sh(["git", "status", "--porcelain"]).strip() + "\n```\n")

    parts.append("## Latest commit\n")
    parts.append("```\n" + try_sh(["git", "log", "-1", "--oneline"]).strip() + "\n```\n")

    parts.append("## Diffstat (HEAD)\n")
    parts.append("```\n" + try_sh(["git", "show", "--stat", "--oneline", "--no-patch"]).strip() + "\n```\n")

    if args.cmd:
        parts.append("## Commands\n")
        for c in args.cmd:
            parts.append(f"### `{c}`\n")
            out = try_sh(["/bin/bash", "-lc", c]).rstrip("\n")
            parts.append("```\n" + out + "\n```\n")

    outp.write_text("\n".join(parts), encoding="utf-8")
    print(str(outp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
