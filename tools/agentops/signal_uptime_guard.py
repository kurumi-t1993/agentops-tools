#!/usr/bin/env python3
"""signal_uptime_guard.py

Local-only Signal bridge guard for signal-cli daemon on 127.0.0.1:8080.

Safety goals:
- Never touch the public internet.
- Prefer targeted process handling (avoid broad pkill patterns).
- Only kill the process that is actually listening on port 8080.
- Log outcomes to memory/metrics/signal-uptime.log.

Behavior:
- If probe succeeds: append "UP" line and exit.
- If probe fails: attempt restart:
  - identify pid listening on TCP:8080
  - terminate it gracefully, then force if needed
  - start signal-cli daemon bound to 127.0.0.1
  - re-probe
  - append RESTARTED_OK or RESTART_FAILED

No external deps.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


LOG_PATH = Path("/Users/day/.openclaw/workspace/memory/metrics/signal-uptime.log")
DAEMON_LOG = Path("/tmp/openclaw-signal-daemon.log")


def now_jst_iso() -> str:
    # Use system tz; include offset
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sh(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def probe() -> bool:
    p = sh(["curl", "-m", "2", "-sS", "-D", "-", "http://127.0.0.1:8080/", "-o", "/dev/null"], timeout=5)
    return p.returncode == 0


def pid_listening_8080() -> Optional[int]:
    p = sh(["lsof", "-nP", "-iTCP:8080", "-sTCP:LISTEN", "-t"], timeout=5)
    if p.returncode != 0:
        return None
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def kill_pid(pid: int) -> None:
    # Try TERM then KILL
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return
    except PermissionError:
        return

    for _ in range(10):
        time.sleep(0.2)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            break

    try:
        os.kill(pid, 9)
    except Exception:
        pass


def start_daemon() -> None:
    # nohup-like start
    with open(DAEMON_LOG, "a", encoding="utf-8") as lf:
        subprocess.Popen(
            ["signal-cli", "daemon", "--http", "127.0.0.1:8080", "--no-receive-stdout"],
            stdout=lf,
            stderr=lf,
            start_new_session=True,
        )


def append_log(status: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{now_jst_iso()} {status}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Signal uptime guard (localhost only).")
    ap.add_argument("--quiet-hours", default="00:00-07:00", help="JST quiet hours range; if inside, no-op.")
    args = ap.parse_args(argv)

    # Quiet hours check (local time)
    try:
        start_s, end_s = args.quiet_hours.split("-", 1)
        h1, m1 = [int(x) for x in start_s.split(":")]
        h2, m2 = [int(x) for x in end_s.split(":")]
        now = dt.datetime.now().astimezone()
        start = now.replace(hour=h1, minute=m1, second=0, microsecond=0)
        end = now.replace(hour=h2, minute=m2, second=0, microsecond=0)
        if end <= start:
            # spans midnight
            in_quiet = now >= start or now <= end
        else:
            in_quiet = start <= now <= end
        if in_quiet:
            return 0
    except Exception:
        pass

    if probe():
        append_log("UP")
        return 0

    # restart path
    pid = pid_listening_8080()
    if pid is not None:
        kill_pid(pid)

    start_daemon()
    time.sleep(2)

    if probe():
        append_log("RESTARTED_OK")
        return 0

    append_log("RESTART_FAILED")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
