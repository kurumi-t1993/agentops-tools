#!/usr/bin/env python3
"""metrics_snapshot.py

Take a read-only system resource snapshot on macOS and append it to a per-day metrics log.

Design goals:
- Local-only, no network calls (beyond reading local system state).
- Best-effort: if a command fails, record the error and continue.
- Redact sensitive-ish identifiers (MACs, RFC1918 IPs, emails, tokens, UUIDs, etc.)
  using tools/agentops/redactor.py rules.

Output file:
  /Users/day/.openclaw/workspace/memory/metrics/YYYY-MM-DD.metrics.md

This is intended to be callable from cron/agent jobs via /bin/bash -lc.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from redactor import redact_text


DEFAULT_CMDS: List[Tuple[str, List[str]]] = [
    ("uname -a", ["uname", "-a"]),
    ("uptime", ["uptime"]),
    ("pmset -g batt", ["pmset", "-g", "batt"]),
    ("pmset -g assertions", ["pmset", "-g", "assertions"]),
    (
        "top -l 1 -stats pid,command,cpu,mem,power -o cpu -n 15",
        [
            "top",
            "-l",
            "1",
            "-stats",
            "pid,command,cpu,mem,power",
            "-o",
            "cpu",
            "-n",
            "15",
        ],
    ),
    ("vm_stat", ["vm_stat"]),
    ("iostat -w 1 -c 2", ["iostat", "-w", "1", "-c", "2"]),
    ("netstat -ib | head -n 30", ["netstat", "-ib"]),
]


@dataclass
class CmdResult:
    label: str
    argv: List[str]
    rc: int
    out: str
    err: str


def run_cmd(label: str, argv: List[str], timeout_s: int = 20) -> CmdResult:
    try:
        p = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return CmdResult(label=label, argv=argv, rc=p.returncode, out=p.stdout or "", err=p.stderr or "")
    except Exception as e:
        return CmdResult(label=label, argv=argv, rc=999, out="", err=f"EXCEPTION: {e}")


def redact_block(text: str) -> str:
    redacted, _ = redact_text(text)
    return redacted


def today_metrics_path(root: Path, tz_name: str = "Asia/Tokyo") -> Path:
    # Use system TZ conversion by calling date? We avoid shell; use local time as best effort.
    # On this Mac, system TZ is already JST; still allow override.
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return root / f"{now:%Y-%m-%d}.metrics.md"


def append_snapshot(path: Path, tz_name: str, cmds: List[Tuple[str, List[str]]]) -> None:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        stamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append("")
    lines.append(f"## Snapshot @ {stamp}")
    lines.append("")

    for label, argv in cmds:
        res = run_cmd(label, argv)
        out = res.out

        # Special-case netstat -ib: emulate `| head -n 30` in-process.
        if label.startswith("netstat -ib"):
            out_lines = out.splitlines()[:30]
            out = "\n".join(out_lines) + ("\n" if out_lines else "")

        block = out
        if res.rc != 0:
            block = (block or "") + ("\n" if block and not block.endswith("\n") else "")
            block += f"[command exited {res.rc}]\n"
        if res.err:
            block += ("\n" if block and not block.endswith("\n") else "")
            block += f"[stderr]\n{res.err}\n"

        block = redact_block(block)

        lines.append(f"### {label}")
        lines.append("```")
        lines.append(block.rstrip("\n"))
        lines.append("```")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Append a redacted metrics snapshot to the daily log.")
    ap.add_argument("--tz", default="Asia/Tokyo")
    ap.add_argument(
        "--outdir",
        default="/Users/day/.openclaw/workspace/memory/metrics",
        help="Directory where YYYY-MM-DD.metrics.md lives.",
    )
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    outpath = today_metrics_path(outdir, tz_name=args.tz)
    append_snapshot(outpath, tz_name=args.tz, cmds=DEFAULT_CMDS)
    print(str(outpath))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
