#!/usr/bin/env python3
"""ops_dashboard.py

Generate a simple offline HTML dashboard from local metrics logs.

Inputs (defaults are OpenClaw workspace paths):
- memory/metrics/signal-uptime.log
- memory/metrics/YYYY-MM-DD.metrics.md (latest N days)

Outputs:
- an HTML file with:
  - last N uptime probes (UP/RESTART...)
  - recent snapshot timestamps
  - quick 'top processes' table for the latest snapshot (best-effort parsing)

Offline-first. No deps.
"""

from __future__ import annotations

import argparse
import glob
import html
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


RE_SNAPSHOT = re.compile(r"^##\s+Snapshot\s+@\s+(.*)$")


def read_tail(path: Path, n: int) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-n:]


def find_latest_metrics_files(metrics_dir: Path, days: int) -> List[Path]:
    files = sorted(metrics_dir.glob("*.metrics.md"))
    return files[-days:]


def extract_snapshots(md_text: str) -> List[str]:
    out: List[str] = []
    for line in md_text.splitlines():
        m = RE_SNAPSHOT.match(line.strip())
        if m:
            out.append(m.group(1).strip())
    return out


def extract_latest_top_block(md_text: str) -> List[Tuple[str, str, str, str, str]]:
    # best-effort parse of the last "### top ..." block rows: PID COMMAND %CPU MEM POWER
    lines = md_text.splitlines()
    # find last occurrence of '### top'
    idx = -1
    for i, line in enumerate(lines):
        if line.startswith("### top "):
            idx = i
    if idx == -1:
        return []

    # find fenced code after it
    j = idx
    while j < len(lines) and lines[j].strip() != "```":
        j += 1
    if j >= len(lines):
        return []
    j += 1
    block: List[str] = []
    while j < len(lines) and lines[j].strip() != "```":
        block.append(lines[j])
        j += 1

    rows: List[Tuple[str, str, str, str, str]] = []
    # find header row starting with PID
    start = None
    for k, line in enumerate(block):
        if line.strip().startswith("PID"):
            start = k + 1
            break
    if start is None:
        return []

    for line in block[start:start + 20]:
        parts = line.split()
        if len(parts) < 5:
            continue
        pid = parts[0]
        cpu = parts[-3]
        mem = parts[-2]
        power = parts[-1]
        command = " ".join(parts[1:-3])
        rows.append((pid, command, cpu, mem, power))
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate an offline ops dashboard HTML.")
    ap.add_argument("--metrics-dir", default="/Users/day/.openclaw/workspace/memory/metrics")
    ap.add_argument("--out", default="/Users/day/.openclaw/workspace/memory/metrics/dashboard.html")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--uptime-lines", type=int, default=200)
    args = ap.parse_args(argv)

    metrics_dir = Path(args.metrics_dir)
    out = Path(args.out)

    uptime_path = metrics_dir / "signal-uptime.log"
    uptime_tail = read_tail(uptime_path, args.uptime_lines)

    metric_files = find_latest_metrics_files(metrics_dir, args.days)
    snapshots: List[str] = []
    top_rows: List[Tuple[str, str, str, str, str]] = []

    latest_md = ""
    if metric_files:
        latest_md = metric_files[-1].read_text(encoding="utf-8", errors="ignore")
        top_rows = extract_latest_top_block(latest_md)
        for fp in metric_files:
            snapshots.extend(extract_snapshots(fp.read_text(encoding="utf-8", errors="ignore")))

    now = datetime.now().astimezone().isoformat(timespec="seconds")

    def esc(s: str) -> str:
        return html.escape(s)

    html_out: List[str] = []
    html_out.append("<!doctype html><html><head><meta charset='utf-8'>")
    html_out.append("<title>AgentOps Dashboard</title>")
    html_out.append("<style>body{font-family:ui-sans-serif,system-ui;max-width:980px;margin:24px auto;padding:0 12px} pre{background:#111;color:#eee;padding:12px;overflow:auto} table{border-collapse:collapse;width:100%} td,th{border:1px solid #ddd;padding:6px} th{background:#f4f4f4;text-align:left} .muted{color:#666}</style>")
    html_out.append("</head><body>")
    html_out.append(f"<h1>AgentOps Dashboard</h1><p class='muted'>Generated {esc(now)}</p>")

    html_out.append("<h2>Signal uptime (tail)</h2>")
    if uptime_tail:
        html_out.append("<pre>" + esc("\n".join(uptime_tail)) + "</pre>")
    else:
        html_out.append("<p class='muted'>(no uptime log found)</p>")

    html_out.append("<h2>Recent metrics snapshots</h2>")
    if snapshots:
        html_out.append("<pre>" + esc("\n".join(snapshots[-200:])) + "</pre>")
    else:
        html_out.append("<p class='muted'>(no snapshots found)</p>")

    html_out.append("<h2>Latest top processes (best-effort)</h2>")
    if top_rows:
        html_out.append("<table><thead><tr><th>PID</th><th>COMMAND</th><th>%CPU</th><th>MEM</th><th>POWER</th></tr></thead><tbody>")
        for pid, cmd, cpu, mem, power in top_rows:
            html_out.append(f"<tr><td>{esc(pid)}</td><td>{esc(cmd)}</td><td>{esc(cpu)}</td><td>{esc(mem)}</td><td>{esc(power)}</td></tr>")
        html_out.append("</tbody></table>")
    else:
        html_out.append("<p class='muted'>(could not parse top block)</p>")

    html_out.append("</body></html>")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(html_out), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
