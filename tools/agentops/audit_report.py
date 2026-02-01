#!/usr/bin/env python3
"""audit_report.py

Offline audit report generator for AgentOps:
- reads a *sanitized* cron snapshot JSON (from cron_sanitize.py)
- compares against the previous snapshot (if present)
- emits a short markdown report

This is meant to be run by a cron/agent job that first obtains cron list output
and sanitizes it.

No deps.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def job_key(j: Dict[str, Any]) -> str:
    return str(j.get("id") or j.get("name") or "?")


def pick_fields(j: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": j.get("id"),
        "name": j.get("name"),
        "enabled": j.get("enabled"),
        "schedule": j.get("schedule"),
        "sessionTarget": j.get("sessionTarget"),
        "payloadKind": (j.get("payload") or {}).get("kind"),
        "timeoutSeconds": (j.get("payload") or {}).get("timeoutSeconds"),
    }


def diff_jobs(prev: List[Dict[str, Any]], cur: List[Dict[str, Any]]):
    pmap = {job_key(j): pick_fields(j) for j in prev}
    cmap = {job_key(j): pick_fields(j) for j in cur}

    added = [cmap[k] for k in cmap.keys() - pmap.keys()]
    removed = [pmap[k] for k in pmap.keys() - cmap.keys()]

    changed: List[Tuple[Dict[str, Any], Dict[str, Any], List[str]]] = []
    for k in cmap.keys() & pmap.keys():
        a = pmap[k]
        b = cmap[k]
        fields = []
        for f in ["name", "enabled", "schedule", "sessionTarget", "payloadKind", "timeoutSeconds"]:
            if a.get(f) != b.get(f):
                fields.append(f)
        if fields:
            changed.append((a, b, fields))

    return added, removed, changed


def format_job(j: Dict[str, Any]) -> str:
    return f"- `{j.get('id')}` **{j.get('name')}** ({'enabled' if j.get('enabled') else 'disabled'})"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a cron audit report from sanitized JSON snapshots.")
    ap.add_argument("--current", required=True, help="Path to current sanitized cron snapshot JSON.")
    ap.add_argument("--previous", default=None, help="Path to previous sanitized cron snapshot JSON.")
    ap.add_argument("--out", required=True, help="Output markdown path.")
    args = ap.parse_args(argv)

    cur = load(Path(args.current)).get("jobs") or []
    prev = []
    if args.previous and Path(args.previous).exists():
        prev = load(Path(args.previous)).get("jobs") or []

    added, removed, changed = diff_jobs(prev, cur)

    lines: List[str] = []
    lines.append(f"# AgentOps audit ({_now()})\n")
    lines.append(f"Jobs in current snapshot: **{len(cur)}**\n")

    if not prev:
        lines.append("(No previous snapshot found — baseline created.)\n")
    else:
        lines.append(f"Changes vs previous snapshot:\n")
        lines.append(f"- Added: **{len(added)}**")
        lines.append(f"- Removed: **{len(removed)}**")
        lines.append(f"- Changed: **{len(changed)}**\n")

    if added:
        lines.append("## Added\n")
        lines.extend(format_job(j) for j in added)
        lines.append("")
    if removed:
        lines.append("## Removed\n")
        lines.extend(format_job(j) for j in removed)
        lines.append("")
    if changed:
        lines.append("## Changed\n")
        for a, b, fields in changed:
            lines.append(f"- `{a.get('id')}` **{a.get('name')}** changed fields: {', '.join(fields)}")
        lines.append("")

    # Always include a short safety checklist
    lines.append("## Safety checklist\n")
    lines.append("- No new jobs should run destructive commands without explicit approval.")
    lines.append("- Any job that sends messages externally should be intentional and minimal.")
    lines.append("- Keep identifier-bearing snapshots local or sanitized before sharing.")

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(str(outp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
