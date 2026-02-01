#!/usr/bin/env python3
"""dep_vet.py

Dependency/package vetting helper for pip (PyPI) and npm.

Design goals:
- Default is *offline*: analyze provided metadata JSON (no network).
- Optional online fetch is guarded behind an explicit flag AND an explicit env var.
  This prevents accidental public internet access.

Online mode:
- --online requires env ALLOW_PUBLIC_INTERNET=1
- Uses public registry JSON endpoints:
  - PyPI: https://pypi.org/pypi/<name>/json
  - npm : https://registry.npmjs.org/<name>

It produces a human-readable risk report + a simple score.

This is heuristic; it is not a guarantee of safety.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


@dataclass
class Result:
    ecosystem: str
    name: str
    score: int
    risk: str
    summary: str
    details: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_json(url: str, timeout: int = 10) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "agentops-dep-vet/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read().decode("utf-8", errors="replace")
    return json.loads(data)


def _require_online_allowed(online: bool) -> None:
    if not online:
        return
    if os.environ.get("ALLOW_PUBLIC_INTERNET") != "1":
        raise SystemExit(
            "Online fetch blocked. To allow public internet fetch, set ALLOW_PUBLIC_INTERNET=1 and pass --online."
        )


def _days_since(dt_str: str) -> Optional[int]:
    # best effort ISO8601 parse
    try:
        # normalize Z
        s = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return int((now - dt.astimezone(timezone.utc)).total_seconds() // 86400)
    except Exception:
        return None


def _risk_bucket(score: int) -> str:
    if score >= 80:
        return "LOW"
    if score >= 55:
        return "MEDIUM"
    return "HIGH"


def vet_pypi(meta: Dict[str, Any], name: str) -> Result:
    info = meta.get("info") or {}
    releases = meta.get("releases") or {}

    score = 50
    notes = []

    # basic signals
    if info.get("home_page") or info.get("project_urls"):
        score += 10
    if info.get("license"):
        score += 5

    # release recency
    upload_time = None
    if info.get("version") and releases.get(info.get("version")):
        files = releases[info["version"]]
        if files and isinstance(files, list):
            upload_time = files[0].get("upload_time_iso_8601") or files[0].get("upload_time")

    if upload_time:
        days = _days_since(upload_time)
        if days is not None:
            if days <= 90:
                score += 10
            elif days <= 365:
                score += 5
            else:
                score -= 5
            notes.append(f"latest release age: ~{days} days")

    # yanked releases (possible issue) — if a lot, reduce score
    yanked_count = 0
    total_files = 0
    for ver, files in releases.items():
        if not files:
            continue
        for f in files:
            total_files += 1
            if f.get("yanked"):
                yanked_count += 1
    if total_files:
        frac = yanked_count / total_files
        if frac > 0.1:
            score -= 10
            notes.append("many yanked files")

    # suspicious name patterns (typosquat-ish)
    if re.search(r"(?i)(\. |\s)", name):
        score -= 10
    if len(name) <= 2:
        score -= 10

    # clamp
    score = max(0, min(100, score))
    risk = _risk_bucket(score)

    summary = "; ".join([n for n in notes if n]) or "basic metadata checks only"
    details = {
        "version": info.get("version"),
        "summary": info.get("summary"),
        "author": info.get("author"),
        "maintainer": info.get("maintainer"),
        "project_urls": info.get("project_urls"),
        "home_page": info.get("home_page"),
        "license": info.get("license"),
        "yanked_files": yanked_count,
        "total_files": total_files,
        "checked_at": _utc_now(),
    }

    return Result(ecosystem="pypi", name=name, score=score, risk=risk, summary=summary, details=details)


def vet_npm(meta: Dict[str, Any], name: str) -> Result:
    score = 50
    notes = []

    latest = None
    dist_tags = meta.get("dist-tags") or {}
    latest = dist_tags.get("latest")

    time = meta.get("time") or {}
    if latest and time.get(latest):
        days = _days_since(time[latest])
        if days is not None:
            if days <= 90:
                score += 10
            elif days <= 365:
                score += 5
            else:
                score -= 5
            notes.append(f"latest release age: ~{days} days")

    # repository link
    repo = meta.get("repository")
    if repo:
        score += 10

    # maintainers
    maintainers = meta.get("maintainers") or []
    if maintainers:
        score += 5

    # very large package can be riskier (heuristic)
    versions = meta.get("versions") or {}
    if len(versions) > 500:
        score -= 5
        notes.append("very large version history")

    score = max(0, min(100, score))
    risk = _risk_bucket(score)

    summary = "; ".join([n for n in notes if n]) or "basic metadata checks only"
    details = {
        "latest": latest,
        "repository": repo,
        "maintainers_count": len(maintainers) if isinstance(maintainers, list) else None,
        "checked_at": _utc_now(),
    }

    return Result(ecosystem="npm", name=name, score=score, risk=risk, summary=summary, details=details)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Vetting helper for PyPI/npm packages.")
    ap.add_argument("--ecosystem", choices=["pypi", "npm"], required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--in", dest="inp", default=None, help="Path to registry metadata JSON (offline mode).")
    ap.add_argument("--online", action="store_true", help="Fetch registry metadata from public internet (guarded).")
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON result.")
    args = ap.parse_args(argv)

    _require_online_allowed(args.online)

    meta: Dict[str, Any]

    if args.inp:
        meta = json.load(open(args.inp, "r", encoding="utf-8"))
    elif args.online:
        if args.ecosystem == "pypi":
            url = f"https://pypi.org/pypi/{args.name}/json"
        else:
            url = f"https://registry.npmjs.org/{args.name}"
        try:
            meta = _fetch_json(url)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Fetch failed ({e.code}) for {url}")
        except Exception as e:
            raise SystemExit(f"Fetch failed for {url}: {e}")
    else:
        raise SystemExit("Provide --in <file.json> (offline) or use --online (guarded).")

    if args.ecosystem == "pypi":
        res = vet_pypi(meta, args.name)
    else:
        res = vet_npm(meta, args.name)

    if args.json:
        print(json.dumps(res.__dict__, indent=2, ensure_ascii=False))
    else:
        print(f"dep_vet ({res.ecosystem}) {res.name}")
        print(f"  score: {res.score}/100")
        print(f"  risk : {res.risk}")
        print(f"  note : {res.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
