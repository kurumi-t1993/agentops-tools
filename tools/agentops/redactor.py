#!/usr/bin/env python3
"""redactor.py

Offline-first log/text redactor.

Goal: remove accidental secrets/PII from logs/messages before they are written/sent.

Default behavior:
- Read from stdin and write redacted text to stdout.
- Or use --in/--out.

This is intentionally conservative (better to over-redact than leak).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Iterable, List, Pattern, Tuple


REPLACEMENTS = {
    "EMAIL": "[REDACTED_EMAIL]",
    "UUID": "[REDACTED_UUID]",
    "MAC": "[REDACTED_MAC]",
    "LAN_IP": "[REDACTED_LAN_IP]",
    "TOKEN": "[REDACTED_TOKEN]",
    "API_KEY": "[REDACTED_API_KEY]",
    "AUTH": "[REDACTED_AUTH]",
}


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: Pattern[str]
    repl: str


def _compile_rules() -> List[Rule]:
    rules: List[Rule] = []

    # Emails
    rules.append(
        Rule(
            "email",
            re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
            REPLACEMENTS["EMAIL"],
        )
    )

    # UUIDs (v1-v5-ish)
    rules.append(
        Rule(
            "uuid",
            re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
            REPLACEMENTS["UUID"],
        )
    )

    # MAC addresses
    rules.append(
        Rule(
            "mac",
            re.compile(r"\b(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b", re.IGNORECASE),
            REPLACEMENTS["MAC"],
        )
    )

    # Private IPv4 ranges (best-effort) + loopback is allowed but still could be redacted if desired.
    # Keep localhost visible by default; redact only RFC1918 + link-local.
    rules.append(
        Rule(
            "lan_ip",
            re.compile(
                r"\b(?:"
                r"10(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}"
                r"|172\.(?:1[6-9]|2\d|3[0-1])(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){2}"
                r"|192\.168(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){2}"
                r"|169\.254(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){2}"
                r")\b"
            ),
            REPLACEMENTS["LAN_IP"],
        )
    )

    # Authorization headers and bearer tokens
    rules.append(
        Rule(
            "auth_header",
            re.compile(r"(?im)^(authorization\s*:\s*)(.+)$"),
            r"\1" + REPLACEMENTS["AUTH"],
        )
    )
    rules.append(
        Rule(
            "bearer",
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-~=+/]+\b"),
            "Bearer " + REPLACEMENTS["TOKEN"],
        )
    )

    # Generic API key-ish patterns (AWS-like, Stripe-like, GitHub tokens, etc.)
    # We keep these heuristic and broad.
    rules.append(
        Rule(
            "aws_access_key_id",
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            REPLACEMENTS["API_KEY"],
        )
    )
    rules.append(
        Rule(
            "github_pat",
            re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
            REPLACEMENTS["API_KEY"],
        )
    )
    rules.append(
        Rule(
            "slack_token",
            re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
            REPLACEMENTS["API_KEY"],
        )
    )
    rules.append(
        Rule(
            "stripe_keys",
            re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{10,}\b"),
            REPLACEMENTS["API_KEY"],
        )
    )

    # Common inline key-value secrets
    rules.append(
        Rule(
            "kv_secrets",
            re.compile(
                r"(?i)\b("
                r"api[_-]?key|secret|token|access[_-]?token|refresh[_-]?token|password|passwd|pwd|private[_-]?key"
                r")\b\s*([=:])\s*([^\s'\"\\]+|\"[^\"]+\"|'[^']+')"
            ),
            lambda m: f"{m.group(1)}{m.group(2)}{REPLACEMENTS['TOKEN']}",
        )
    )

    return rules


RULES = _compile_rules()


def redact_text(text: str) -> Tuple[str, List[str]]:
    """Return (redacted_text, applied_rule_names)."""
    applied: List[str] = []
    out = text
    for rule in RULES:
        new = rule.pattern.sub(rule.repl, out)
        if new != out:
            applied.append(rule.name)
            out = new
    return out, applied


def _read_all(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write_all(path: str | None, content: str) -> None:
    if not path or path == "-":
        sys.stdout.write(content)
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Redact secrets/PII from text/logs.")
    p.add_argument("--in", dest="inp", help="Input file path (or - for stdin).", default="-")
    p.add_argument("--out", dest="out", help="Output file path (or - for stdout).", default="-")
    p.add_argument("--report", action="store_true", help="Print which rule types were applied to stderr.")
    args = p.parse_args(argv)

    text = _read_all(args.inp)
    redacted, applied = redact_text(text)
    _write_all(args.out, redacted)

    if args.report:
        uniq = sorted(set(applied))
        sys.stderr.write(f"Applied rules: {', '.join(uniq) if uniq else 'none'}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
