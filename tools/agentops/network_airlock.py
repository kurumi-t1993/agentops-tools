#!/usr/bin/env python3
"""network_airlock.py

Run a command with outbound network access blocked (except localhost), *when possible*.

On macOS, we can often use `sandbox-exec` with a minimal profile that denies network.
This is not a perfect security boundary, but it's a very useful guardrail to prevent
accidental internet access during local testing.

Behavior:
- If sandbox-exec is available: run the command under a profile that denies network.
- If not available: run normally but WARN (or fail with --require).

No external dependencies.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List


SANDBOX_PROFILE = r"""
(version 1)
(allow default)
; deny all network (both inbound/outbound)
(deny network*)
""".lstrip()


def have_sandbox_exec() -> bool:
    return shutil.which("sandbox-exec") is not None


def run_under_sandbox(cmd: List[str]) -> int:
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="airlock-", suffix=".sb") as f:
        f.write(SANDBOX_PROFILE)
        profile_path = f.name
    try:
        p = subprocess.run(["sandbox-exec", "-f", profile_path, *cmd])
        return int(p.returncode)
    finally:
        try:
            os.unlink(profile_path)
        except OSError:
            pass


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a command with network blocked when possible.")
    ap.add_argument("--require", action="store_true", help="Fail if sandboxing is unavailable.")
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run (prefix with --).")
    args = ap.parse_args(argv)

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        ap.error("No command provided. Example: network_airlock.py -- python3 -c 'print(123)'")

    if have_sandbox_exec():
        return run_under_sandbox(cmd)

    if args.require:
        sys.stderr.write("network_airlock: sandbox-exec not available; refusing to run (use without --require to run anyway)\n")
        return 2

    sys.stderr.write("network_airlock: WARNING sandbox-exec not available; running without network isolation\n")
    p = subprocess.run(cmd)
    return int(p.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
