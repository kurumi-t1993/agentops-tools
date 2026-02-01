#!/usr/bin/env python3
"""regression_harness.py

Very small regression test harness for agent/tool outputs.

Concept:
- A "case" is a command to run + expected stdout snapshot.
- Store cases in a JSON file.

Modes:
- record: run commands and write snapshots
- check : run commands and compare to snapshots (diff on mismatch)

This is intended for local scripts (no internet). Use with network_airlock if desired.

No deps.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Case:
    name: str
    cmd: str
    expect: str = ""


def run(cmd: str) -> str:
    p = subprocess.run(["/bin/bash", "-lc", cmd], capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" if p.stdout and not p.stdout.endswith("\n") else "")
    if p.stderr:
        out += "[stderr]\n" + p.stderr
    if p.returncode != 0:
        out += f"[exit {p.returncode}]\n"
    return out


def load_cases(path: Path) -> List[Case]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Case(**c) for c in data.get("cases", [])]


def save_cases(path: Path, cases: List[Case]) -> None:
    data = {"cases": [c.__dict__ for c in cases]}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def diff(a: str, b: str) -> str:
    import difflib

    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), fromfile="expected", tofile="actual"))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Snapshot-based regression test harness.")
    ap.add_argument("--cases", required=True, help="JSON file containing cases.")
    ap.add_argument("--mode", choices=["record", "check"], default="check")
    args = ap.parse_args(argv)

    path = Path(args.cases)
    cases = load_cases(path)

    if args.mode == "record":
        for c in cases:
            c.expect = run(c.cmd)
        save_cases(path, cases)
        print(f"recorded {len(cases)} case(s)")
        return 0

    # check
    ok = True
    for c in cases:
        actual = run(c.cmd)
        if actual != c.expect:
            ok = False
            sys.stderr.write(f"CASE FAILED: {c.name}\n")
            sys.stderr.write(diff(c.expect, actual) + "\n")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
