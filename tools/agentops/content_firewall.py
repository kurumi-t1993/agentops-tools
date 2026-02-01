#!/usr/bin/env python3
"""content_firewall.py

Prompt-injection / instruction-scent firewall for untrusted text.

This is NOT a perfect defense. The goal is pragmatic:
- When we ingest web content, treat it as data.
- Detect and optionally strip/flag instruction-like segments that try to control tools or override rules.

Offline-first. No dependencies.

Usage:
  cat page.txt | python3 content_firewall.py --mode strip

Modes:
- report: do not modify text; print findings to stderr; output original text.
- strip : remove suspicious lines/blocks; output sanitized text.
- mask  : replace suspicious lines with a placeholder.

"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Finding:
    kind: str
    line_no: int
    excerpt: str


# Heuristics: catch common prompt-injection patterns.
PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        "override_rules",
        re.compile(
            r"(?i)\b(ignore|disregard|override)\b.*\b(previous|earlier|system|developer|instructions|rules)\b"
        ),
    ),
    (
        "tool_command",
        re.compile(r"(?i)\b(run|execute|shell|terminal|command|curl|wget|powershell|bash|zsh)\b"),
    ),
    (
        "credential_request",
        re.compile(r"(?i)\b(password|passcode|2fa|otp|api\s*key|secret\s*key|recovery\s*code)\b"),
    ),
    (
        "external_action",
        re.compile(r"(?i)\b(send\s+(a\s+)?message|post\s+to|tweet|dm|email|transfer\s+money)\b"),
    ),
    (
        "self_referential_prompt",
        re.compile(r"(?i)\b(as\s+an\s+ai|you\s+are\s+chatgpt|system\s+prompt|developer\s+message)\b"),
    ),
    (
        "delimiters",
        re.compile(r"(?i)^(\s*```|\s*<\/?(system|assistant|developer|tool)>|\s*\[\s*system\s*\])"),
    ),
]


def analyze(text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        l = line.strip()
        if not l:
            continue
        for kind, pat in PATTERNS:
            if pat.search(line):
                excerpt = (l[:180] + "…") if len(l) > 180 else l
                findings.append(Finding(kind=kind, line_no=i, excerpt=excerpt))
                break
    return findings


def sanitize(text: str, mode: str) -> Tuple[str, List[Finding]]:
    findings = analyze(text)
    if mode == "report" or not findings:
        return text, findings

    bad_lines = {f.line_no for f in findings}
    out_lines: List[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if i in bad_lines:
            if mode == "strip":
                continue
            if mode == "mask":
                out_lines.append("[CONTENT_FIREWALL_REDACTED]")
                continue
        out_lines.append(line)

    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), findings


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect/strip instruction-like text from untrusted sources.")
    ap.add_argument("--mode", choices=["report", "strip", "mask"], default="report")
    ap.add_argument("--max-findings", type=int, default=50)
    args = ap.parse_args(argv)

    text = sys.stdin.read()
    out, findings = sanitize(text, args.mode)

    if findings:
        sys.stderr.write(f"content_firewall: {len(findings)} suspicious line(s) detected\n")
        for f in findings[: args.max_findings]:
            sys.stderr.write(f"  L{f.line_no}: {f.kind}: {f.excerpt}\n")
        if len(findings) > args.max_findings:
            sys.stderr.write(f"  … +{len(findings)-args.max_findings} more\n")

    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
