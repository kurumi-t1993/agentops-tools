#!/usr/bin/env python3
"""policy_gate.py

Simple local policy gate for agent tooling.

Motivation: before running a command or performing an action, check whether it's
allowed by a project policy manifest.

This is not meant to be bulletproof security—it's a guardrail and documentation.

Policy file (YAML-lite, parsed without dependencies):

allowed:
  exec: true
  network: false
  message: false
  write_paths:
    - /Users/day/.openclaw/workspace/
    - ./
blocked_cmd_patterns:
  - '\\bcurl\\b'
  - '\\bwget\\b'

We intentionally support a tiny subset:
- booleans for exec/network/message
- list of write_paths (prefix allowlist)
- list of blocked_cmd_patterns (regex strings)

Usage:
  python3 policy_gate.py --policy policy.txt --check-cmd "python3 -m unittest -q"
  python3 policy_gate.py --policy policy.txt --check-write /Users/day/.openclaw/workspace/tools/x.py

Exit codes:
- 0 allowed
- 2 blocked
- 1 parse/usage error

Offline-first. No deps.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Policy:
    allow_exec: bool = False
    allow_network: bool = False
    allow_message: bool = False
    write_paths: List[str] = None
    blocked_cmd_patterns: List[str] = None


def _default_list(x):
    return x if x is not None else []


def parse_policy(text: str) -> Policy:
    # Minimal indentation-based parser. Not general YAML.
    p = Policy(write_paths=[], blocked_cmd_patterns=[])
    section = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            continue
        if ":" in line and not line.lstrip().startswith("-"):
            k, v = line.split(":", 1)
            key = k.strip()
            val = v.strip().lower()
            if section == "allowed":
                if key == "exec":
                    p.allow_exec = val == "true"
                elif key == "network":
                    p.allow_network = val == "true"
                elif key == "message":
                    p.allow_message = val == "true"
            continue
        if line.lstrip().startswith("-"):
            item = line.lstrip()[1:].strip()
            item = item.strip('"').strip("'")
            if section == "allowed" and item.startswith("/"):
                # ignore
                continue
            if section == "blocked_cmd_patterns":
                p.blocked_cmd_patterns.append(item)
            elif section == "allowed":
                # ignore
                pass
            elif section == "write_paths":
                p.write_paths.append(item)
            elif section == "allowed" and item:
                pass
            else:
                # support top-level write_paths:
                if section == "write_paths":
                    p.write_paths.append(item)
    return p


def is_write_allowed(path: str, policy: Policy) -> bool:
    ap = os.path.abspath(path)
    for pref in _default_list(policy.write_paths):
        if not pref:
            continue
        # allow relative prefixes
        if pref.startswith("./"):
            pref_abs = os.path.abspath(pref)
        else:
            pref_abs = os.path.abspath(pref)
        if ap.startswith(pref_abs):
            return True
    return False


def is_cmd_allowed(cmd: str, policy: Policy) -> Tuple[bool, Optional[str]]:
    for pat in _default_list(policy.blocked_cmd_patterns):
        try:
            if re.search(pat, cmd):
                return False, f"blocked by pattern: {pat}"
        except re.error:
            return False, f"invalid regex in blocked_cmd_patterns: {pat}"
    return True, None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Check actions against a simple policy manifest.")
    ap.add_argument("--policy", required=True, help="Path to policy file.")
    ap.add_argument("--check-cmd", default=None, help="Command string to check.")
    ap.add_argument("--check-write", default=None, help="Path intended for write.")
    ap.add_argument("--require-exec", action="store_true")
    ap.add_argument("--require-network", action="store_true")
    ap.add_argument("--require-message", action="store_true")
    args = ap.parse_args(argv)

    policy_text = Path(args.policy).read_text(encoding="utf-8", errors="ignore")
    policy = parse_policy(policy_text)

    if args.require_exec and not policy.allow_exec:
        sys.stderr.write("policy_gate: exec not allowed\n")
        return 2
    if args.require_network and not policy.allow_network:
        sys.stderr.write("policy_gate: network not allowed\n")
        return 2
    if args.require_message and not policy.allow_message:
        sys.stderr.write("policy_gate: message not allowed\n")
        return 2

    if args.check_cmd is not None:
        ok, reason = is_cmd_allowed(args.check_cmd, policy)
        if not ok:
            sys.stderr.write(f"policy_gate: command blocked: {reason}\n")
            return 2

    if args.check_write is not None:
        if not is_write_allowed(args.check_write, policy):
            sys.stderr.write("policy_gate: write path not allowed\n")
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
