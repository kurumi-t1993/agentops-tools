#!/usr/bin/env python3
"""secrets_scan.py

Local secrets/PII scanner for git repos.

Primary use:
- Scan staged changes before commit (pre-commit hook).
- Scan tracked files for obvious secret patterns.

This is heuristic. Goal is to catch *accidents* (tokens, keys, auth headers, etc.).

No dependencies.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


DEFAULT_ALLOWLIST_PATH = ".secrets_allowlist"


@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    kind: str
    excerpt: str


PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe_secret", re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{10,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA|PRIVATE) KEY-----")),
    ("auth_header", re.compile(r"(?i)^\s*authorization\s*:\s*.+$")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-~=+/]{10,}\b")),
    ("kv_secret", re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*\S+")),
]


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    ent = 0.0
    n = len(s)
    for c in freq.values():
        p = c / n
        ent -= p * math.log2(p)
    return ent


ENTROPY_CANDIDATE = re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")


def load_allowlist(path: str) -> List[re.Pattern[str]]:
    if not os.path.exists(path):
        return []
    pats: List[re.Pattern[str]] = []
    for line in open(path, "r", encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # treat as regex
        pats.append(re.compile(line))
    return pats


def is_allowed(line: str, allowlist: Sequence[re.Pattern[str]]) -> bool:
    return any(p.search(line) for p in allowlist)


def scan_text(text: str, path: str, allowlist: Sequence[re.Pattern[str]]) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if is_allowed(line, allowlist):
            continue

        for kind, pat in PATTERNS:
            if pat.search(line):
                excerpt = (line.strip()[:180] + "…") if len(line.strip()) > 180 else line.strip()
                findings.append(Finding(path=path, line_no=i, kind=kind, excerpt=excerpt))
                break

        # entropy heuristic: high-entropy tokens in code/comments
        for m in ENTROPY_CANDIDATE.finditer(line):
            token = m.group(0)
            if len(token) < 32:
                continue
            ent = shannon_entropy(token)
            if ent >= 4.2:
                excerpt = (line.strip()[:180] + "…") if len(line.strip()) > 180 else line.strip()
                findings.append(Finding(path=path, line_no=i, kind=f"high_entropy({ent:.2f})", excerpt=excerpt))
                break

    return findings


def read_file(path: str) -> str:
    return open(path, "r", encoding="utf-8", errors="ignore").read()


def git_staged_patch() -> str:
    return subprocess.check_output(["git", "diff", "--cached", "--unified=0"], text=True)


def parse_unified_zero(patch: str) -> List[Tuple[str, int, str]]:
    """Return list of (path, line_no, added_line_text) for added lines.

    This is a best-effort parser for `--unified=0` output.
    """
    out: List[Tuple[str, int, str]] = []
    cur_path = ""
    new_line = 0
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            cur_path = line[6:].strip()
            continue
        if line.startswith("@@"):
            # @@ -old,+new @@
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                new_line = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.append((cur_path, new_line, line[1:]))
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # removal doesn't advance new_line
            continue
        else:
            # context line (shouldn't happen with unified=0, but just in case)
            if cur_path and not line.startswith("\\"):
                new_line += 1
    return out


def scan_staged(allowlist: Sequence[re.Pattern[str]]) -> List[Finding]:
    patch = git_staged_patch()
    added = parse_unified_zero(patch)
    findings: List[Finding] = []
    for path, line_no, txt in added:
        if not path:
            continue
        # allowlist applies to line text
        if is_allowed(txt, allowlist):
            continue
        for kind, pat in PATTERNS:
            if pat.search(txt):
                excerpt = (txt.strip()[:180] + "…") if len(txt.strip()) > 180 else txt.strip()
                findings.append(Finding(path=path, line_no=line_no, kind=kind, excerpt=excerpt))
                break
        else:
            for m in ENTROPY_CANDIDATE.finditer(txt):
                token = m.group(0)
                if len(token) < 32:
                    continue
                ent = shannon_entropy(token)
                if ent >= 4.2:
                    excerpt = (txt.strip()[:180] + "…") if len(txt.strip()) > 180 else txt.strip()
                    findings.append(Finding(path=path, line_no=line_no, kind=f"high_entropy({ent:.2f})", excerpt=excerpt))
                    break
    return findings


def scan_paths(paths: Sequence[str], allowlist: Sequence[re.Pattern[str]]) -> List[Finding]:
    findings: List[Finding] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for fn in files:
                    fp = os.path.join(root, fn)
                    try:
                        findings.extend(scan_text(read_file(fp), fp, allowlist))
                    except Exception:
                        pass
        else:
            try:
                findings.extend(scan_text(read_file(p), p, allowlist))
            except Exception:
                pass
    return findings


def print_findings(findings: Sequence[Finding]) -> None:
    for f in findings:
        sys.stderr.write(f"{f.path}:{f.line_no}: {f.kind}: {f.excerpt}\n")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Scan for likely secrets/PII.")
    ap.add_argument("--staged", action="store_true", help="Scan staged changes (git diff --cached).")
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST_PATH, help="Regex allowlist file.")
    ap.add_argument("--fail", action="store_true", help="Exit non-zero if findings exist.")
    ap.add_argument("paths", nargs="*", help="Paths to scan (files/dirs). If empty and not --staged, scans tracked files.")
    args = ap.parse_args(argv)

    allowlist = load_allowlist(args.allowlist)

    if args.staged:
        findings = scan_staged(allowlist)
    else:
        paths = args.paths
        if not paths:
            # default: scan tracked files
            files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
            findings = scan_paths(files, allowlist)
        else:
            findings = scan_paths(paths, allowlist)

    if findings:
        sys.stderr.write(f"secrets_scan: {len(findings)} potential issue(s) found\n")
        print_findings(findings)
        return 2 if args.fail else 0

    sys.stderr.write("secrets_scan: clean\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
