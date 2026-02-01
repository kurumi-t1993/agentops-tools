#!/usr/bin/env python3
"""install_precommit.py

Installs a pre-commit hook that runs secrets_scan.py on staged changes.

This writes to .git/hooks/pre-commit (not tracked).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


HOOK = """#!/bin/sh
set -eu
# Run secrets scan on staged changes
python3 tools/agentops/secrets_scan.py --staged --fail
"""


def main() -> int:
    git_dir = Path(".git")
    if not git_dir.exists():
        raise SystemExit("Not a git repo (no .git directory)")
    hooks = git_dir / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    path = hooks / "pre-commit"
    path.write_text(HOOK, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
