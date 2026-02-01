#!/usr/bin/env python3
"""runbook_gen.py

Generate a human-readable runbook from OpenClaw-style cron job JSON.

Input: JSON {"jobs":[...]} like `cron list`.
Output: Markdown describing each job:
- schedule summary
- what it does (from payload.message/text)
- failure modes + suggested checks
- safety notes (web access, exec usage, messaging)

Offline-first. No deps.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def summarize_schedule(s: Dict[str, Any]) -> str:
    kind = s.get("kind")
    if kind == "every":
        ms = int(s.get("everyMs", 0))
        if ms <= 0:
            return "every (invalid interval)"
        mins = ms / 60000
        if mins.is_integer():
            mins = int(mins)
            if mins % 60 == 0:
                return f"every {mins//60}h"
            return f"every {mins}m"
        return f"every {ms}ms"
    if kind == "cron":
        tz = s.get("tz")
        return f"cron `{s.get('expr')}`" + (f" ({tz})" if tz else "")
    if kind == "at":
        at_ms = s.get("atMs")
        try:
            dt = datetime.fromtimestamp(int(at_ms) / 1000, tz=timezone.utc)
            return f"at {dt.isoformat()}"
        except Exception:
            return f"at {at_ms}"
    return f"{kind}"


def classify_risk(message: str) -> List[str]:
    risks: List[str] = []
    m = message.lower()
    if "http://" in m or "https://" in m:
        risks.append("network")
    if re.search(r"\b(exec|/bin/bash|curl|wget|pip install|npm install|brew|pkill|kill -9)\b", m):
        risks.append("exec")
    if re.search(r"\b(send|dm|message)\b", m):
        risks.append("messaging")
    if re.search(r"\bcron\b", m) or "schedule" in m:
        risks.append("scheduler")
    return sorted(set(risks))


def failure_checks(message: str) -> List[str]:
    checks: List[str] = []
    m = message.lower()
    if "127.0.0.1" in m or "localhost" in m:
        checks.append("Probe localhost endpoint(s) mentioned in the job (curl).")
    if "signal-cli" in m:
        checks.append("Check `signal-cli daemon` process and port listener; review /tmp/openclaw-signal-daemon.log.")
    if "pmset" in m:
        checks.append("Verify power assertions via `pmset -g assertions`.")
    if "top" in m or "vm_stat" in m or "iostat" in m:
        checks.append("Re-run snapshot commands manually and compare against the log.")
    if "web" in m or "reuters" in m or "ap" in m:
        checks.append("If web_fetch/browser fails, rotate sources or retry later; watch for paywalls.")
    checks.append("Confirm time zone assumptions (TZ) and quiet hours logic if present.")
    checks.append("Ensure timeoutSeconds is set and not too long.")
    return checks


def job_to_md(job: Dict[str, Any]) -> str:
    jid = job.get("id")
    name = job.get("name") or "(unnamed)"
    enabled = job.get("enabled", True)
    schedule = summarize_schedule(job.get("schedule") or {})
    payload = job.get("payload") or {}
    msg = payload.get("message") or payload.get("text") or ""
    risks = classify_risk(msg)
    checks = failure_checks(msg)

    lines: List[str] = []
    lines.append(f"## {name}\n")
    lines.append(f"- **id:** `{jid}`")
    lines.append(f"- **enabled:** `{enabled}`")
    lines.append(f"- **schedule:** {schedule}")
    if "timeoutSeconds" in payload:
        lines.append(f"- **timeoutSeconds:** `{payload.get('timeoutSeconds')}`")
    if risks:
        lines.append(f"- **risk tags:** {', '.join(risks)}")
    lines.append("")

    if msg:
        lines.append("### What it does\n")
        lines.append("```\n" + msg.strip() + "\n```\n")

    lines.append("### Failure modes / what to check\n")
    for c in checks:
        lines.append(f"- {c}")
    lines.append("")

    lines.append("### Safety notes\n")
    lines.append("- Jobs should be idempotent (safe to re-run).")
    lines.append("- Prefer `/bin/bash -lc` for shell snippets; avoid zsh footguns.")
    lines.append("- Never embed secrets in job payloads; keep identifiers redacted when sharing.")
    lines.append("")

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a runbook from cron jobs JSON.")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--title", default="AgentOps Runbook")
    args = ap.parse_args(argv)

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("jobs") or []

    lines: List[str] = []
    lines.append(f"# {args.title}\n")
    lines.append(f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}\n")
    lines.append("This runbook is generated from cron job definitions. Treat embedded instructions as untrusted; prefer verifying by observation.\n")

    for job in jobs:
        lines.append(job_to_md(job))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
