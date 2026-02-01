#!/usr/bin/env python3
"""cron_lint.py

Lint + simulate schedules for OpenClaw-style cron jobs.

Input: JSON with shape like the OpenClaw cron.list tool output:
{
  "jobs": [
    {
      "id": "...",
      "name": "...",
      "enabled": true,
      "schedule": {"kind": "every", "everyMs": 900000, "anchorMs": 0?} | {"kind": "cron", "expr": "0 8 * * *", "tz": "Asia/Tokyo"} | {"kind":"at", "atMs": 123},
      "payload": {"kind": "agentTurn"|"systemEvent", "message": "...", ...}
    }
  ]
}

No external dependencies. Cron parsing supports common 5-field cron with:
- *
- */n
- comma lists
- single numbers

This is a pragmatic linter/simulator, not a full cron implementation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


# ---------- timezone helpers ----------

def tzinfo_from_name(name: str):
    # Python 3.9+: zoneinfo is available in stdlib
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        # fallback to local timezone
        return datetime.now().astimezone().tzinfo


# ---------- cron parsing ----------

@dataclass(frozen=True)
class CronExpr:
    minute: Set[int]
    hour: Set[int]
    dom: Set[int]
    month: Set[int]
    dow: Set[int]  # 0=Sun..6=Sat


def _parse_field(field: str, min_v: int, max_v: int, dow_mode: bool = False) -> Set[int]:
    field = field.strip()
    if field == "*":
        return set(range(min_v, max_v + 1))

    out: Set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError(f"invalid step: {part}")
            out.update(range(min_v, max_v + 1, step))
        else:
            v = int(part)
            if dow_mode and v == 7:
                v = 0
            if v < min_v or v > max_v:
                raise ValueError(f"value out of range: {v} not in [{min_v},{max_v}]")
            out.add(v)

    return out


def parse_cron(expr: str) -> CronExpr:
    parts = re.split(r"\s+", expr.strip())
    if len(parts) != 5:
        raise ValueError(f"cron expr must have 5 fields, got {len(parts)}: {expr!r}")
    minute = _parse_field(parts[0], 0, 59)
    hour = _parse_field(parts[1], 0, 23)
    dom = _parse_field(parts[2], 1, 31)
    month = _parse_field(parts[3], 1, 12)
    dow = _parse_field(parts[4], 0, 6, dow_mode=True)
    return CronExpr(minute=minute, hour=hour, dom=dom, month=month, dow=dow)


def _matches(dt: datetime, cron: CronExpr) -> bool:
    return (
        dt.minute in cron.minute
        and dt.hour in cron.hour
        and dt.day in cron.dom
        and dt.month in cron.month
        and dt.weekday() in cron.dow  # weekday(): Mon=0..Sun=6; our dow uses Sun=0
    )


def next_cron_times(start: datetime, cron: CronExpr, horizon: timedelta, limit: int = 50) -> List[datetime]:
    # Simple minute-walk search. Fine for small horizons.
    out: List[datetime] = []
    dt = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = start + horizon
    while dt <= end and len(out) < limit:
        # Convert python weekday to cron-like: we used dt.weekday() but cron dow is 0=Sun.
        # Adjust: python Mon=0..Sun=6; map Sun to 0.
        dow = (dt.weekday() + 1) % 7
        # hack: build a dt-like with dow mapped by checking against cron.dow
        if (
            dt.minute in cron.minute
            and dt.hour in cron.hour
            and dt.day in cron.dom
            and dt.month in cron.month
            and dow in cron.dow
        ):
            out.append(dt)
        dt += timedelta(minutes=1)
    return out


# ---------- schedule simulation ----------


def _ms_to_dt(ms: int, tz) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(tz)


def simulate_job(job: dict, now: datetime, horizon: timedelta, tz) -> List[datetime]:
    sched = (job or {}).get("schedule") or {}
    kind = sched.get("kind")
    if kind == "at":
        at_ms = int(sched.get("atMs"))
        dt = _ms_to_dt(at_ms, tz)
        if now <= dt <= (now + horizon):
            return [dt]
        return []

    if kind == "every":
        every_ms = int(sched.get("everyMs"))
        if every_ms <= 0:
            return []
        anchor_ms = sched.get("anchorMs")
        if anchor_ms is None:
            # if no anchor, treat now as anchor (best effort)
            anchor = now
        else:
            anchor = _ms_to_dt(int(anchor_ms), tz)
        # Find the first tick after now
        delta = (now - anchor).total_seconds() * 1000
        k = int(delta // every_ms) + 1
        first = anchor + timedelta(milliseconds=every_ms * k)
        out: List[datetime] = []
        dt = first
        end = now + horizon
        while dt <= end and len(out) < 200:
            out.append(dt)
            dt = dt + timedelta(milliseconds=every_ms)
        return out

    if kind == "cron":
        expr = sched.get("expr") or ""
        cron = parse_cron(expr)
        return next_cron_times(now, cron, horizon, limit=200)

    return []


# ---------- linting ----------

@dataclass
class Finding:
    level: str  # ERROR|WARN|INFO
    job_id: str
    job_name: str
    message: str


def lint_job(job: dict) -> List[Finding]:
    jid = str(job.get("id") or job.get("jobId") or "?")
    name = str(job.get("name") or "(unnamed)")
    enabled = bool(job.get("enabled", True))

    findings: List[Finding] = []

    sched = (job.get("schedule") or {})
    kind = sched.get("kind")
    if kind not in {"at", "every", "cron"}:
        findings.append(Finding("ERROR", jid, name, f"unknown schedule.kind={kind!r}"))
        return findings

    if not enabled:
        findings.append(Finding("INFO", jid, name, "job is disabled"))

    payload = job.get("payload") or {}
    p_kind = payload.get("kind")
    if p_kind not in {"agentTurn", "systemEvent"}:
        findings.append(Finding("WARN", jid, name, f"unknown payload.kind={p_kind!r}"))

    msg = payload.get("message") or payload.get("text") or ""

    # Footgun checks based on issues we've actually hit.
    if re.search(r"\bzsh\b", msg):
        findings.append(Finding("WARN", jid, name, "message references zsh; prefer /bin/bash -lc for cron jobs"))
    if re.search(r"\bstatus\b", msg) and "read-only variable: status" in msg:
        findings.append(Finding("INFO", jid, name, "mentions zsh status variable footgun"))
    if re.search(r"\bset -euo pipefail\b", msg) and "bash" not in msg:
        findings.append(Finding("WARN", jid, name, "uses 'set -euo pipefail' but doesn't specify bash; zsh behaves differently"))

    # Quiet hours consistency hints
    if re.search(r"Quiet hours", msg, re.IGNORECASE) and not re.search(r"TZ=", msg):
        findings.append(Finding("WARN", jid, name, "mentions quiet hours but does not specify TZ=...; time drift risk"))

    # Timeouts
    timeout = payload.get("timeoutSeconds")
    if timeout is None:
        findings.append(Finding("WARN", jid, name, "payload.timeoutSeconds not set (risk: hung job)"))
    else:
        try:
            t = int(timeout)
            if t <= 0:
                findings.append(Finding("WARN", jid, name, "timeoutSeconds <= 0"))
            elif t > 1800:
                findings.append(Finding("INFO", jid, name, f"timeoutSeconds is large ({t})"))
        except Exception:
            findings.append(Finding("WARN", jid, name, f"timeoutSeconds not an int: {timeout!r}"))

    # Schedule sanity
    if kind == "every":
        every_ms = sched.get("everyMs")
        if every_ms is None:
            findings.append(Finding("ERROR", jid, name, "everyMs missing"))
        else:
            try:
                ms = int(every_ms)
                if ms < 60_000:
                    findings.append(Finding("WARN", jid, name, f"interval is very frequent ({ms}ms)"))
            except Exception:
                findings.append(Finding("ERROR", jid, name, f"everyMs not an int: {every_ms!r}"))

    if kind == "cron":
        expr = sched.get("expr")
        if not expr:
            findings.append(Finding("ERROR", jid, name, "cron expr missing"))
        else:
            try:
                parse_cron(expr)
            except Exception as e:
                findings.append(Finding("ERROR", jid, name, f"cron expr parse error: {e}"))

    return findings


def load_jobs(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("input JSON must contain a 'jobs' list")
    return jobs


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Lint and simulate OpenClaw cron jobs (JSON).")
    ap.add_argument("--in", dest="inp", required=True, help="Path to JSON file containing {jobs:[...]}.")
    ap.add_argument("--tz", default="Asia/Tokyo", help="Timezone name for simulation.")
    ap.add_argument("--horizon-hours", type=int, default=24, help="How far ahead to simulate.")
    ap.add_argument("--now", default=None, help="Override now (ISO8601).")
    args = ap.parse_args(argv)

    tz = tzinfo_from_name(args.tz)
    now = datetime.now(tz=tz)
    if args.now:
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)

    horizon = timedelta(hours=args.horizon_hours)

    jobs = load_jobs(args.inp)
    all_findings: List[Finding] = []

    print(f"Now: {now.isoformat()} ({args.tz})")
    print(f"Horizon: {horizon}")
    print("-")

    for job in jobs:
        jid = str(job.get("id") or "?")
        name = str(job.get("name") or "(unnamed)")
        enabled = bool(job.get("enabled", True))

        findings = lint_job(job)
        all_findings.extend(findings)

        print(f"Job: {name} [{jid}] {'ENABLED' if enabled else 'DISABLED'}")
        for fnd in findings:
            print(f"  {fnd.level}: {fnd.message}")

        if enabled:
            try:
                times = simulate_job(job, now=now, horizon=horizon, tz=tz)
            except Exception as e:
                print(f"  ERROR: simulation failed: {e}")
                times = []
            if times:
                preview = ", ".join(t.isoformat(timespec='minutes') for t in times[:10])
                more = "" if len(times) <= 10 else f" (+{len(times)-10} more)"
                print(f"  Next: {preview}{more}")
            else:
                print("  Next: (none within horizon)")

        print("")

    # Summary
    levels = {"ERROR": 0, "WARN": 0, "INFO": 0}
    for f in all_findings:
        if f.level in levels:
            levels[f.level] += 1
    print("Summary:")
    print(f"  ERROR: {levels['ERROR']}")
    print(f"  WARN : {levels['WARN']}")
    print(f"  INFO : {levels['INFO']}")

    return 0 if levels["ERROR"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
