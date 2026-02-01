# AgentOps Tools (offline-first)

This folder contains local-first utilities to make agent workflows safer and more reliable.

## Tools

- `redactor.py` — redact secrets/PII from text/logs.
- `cron_lint.py` — lint and simulate cron/interval schedules for OpenClaw-style job JSON.
- `content_firewall.py` — detect/strip instruction-like text from untrusted sources (prompt-injection firewall).
- `network_airlock.py` — run a command with network access blocked (best-effort; macOS uses sandbox-exec when available).
- `secrets_scan.py` — scan staged/tracked files for likely secrets/PII (use with pre-commit).
- `install_precommit.py` — install a pre-commit hook that runs secrets_scan on staged changes.

## Requirements

- Python 3.9+ (no external dependencies).

## Quick start

```bash
cd /Users/day/.openclaw/workspace/tools/agentops
python3 -m unittest -q
```

### Redactor

Redact stdin → stdout:

```bash
echo 'Authorization: Bearer token' | python3 redactor.py
```

Redact a file and write a `.redacted` copy:

```bash
python3 redactor.py --in some.log --out some.log.redacted
```

### Cron linter/simulator

This expects a JSON file shaped like the OpenClaw `cron list` output (an object with a `jobs` array).

```bash
python3 cron_lint.py --in cron_jobs.json --tz Asia/Tokyo --horizon-hours 24
```

It prints:
- lint findings (warnings/errors)
- a schedule preview of each job’s next run(s) within the horizon

Tip: if you don’t have JSON handy, you can paste the `cron list` output from the OpenClaw tools into a file.

### Other utilities

- `dep_vet.py` — offline-first dependency vetting (PyPI/npm) with guarded online fetch.
- `agentops_suite.py` — run tests + secrets scan + (optional) airlock + receipt in one command.
- `policy_gate.py` — lightweight policy manifest gate for commands/writes/capabilities.
- `mock_api.py` — local mock HTTP API server (offline integration testing).
- `regression_harness.py` — snapshot-based regression harness for commands (record/check).
- `cron_sanitize.py` — redact OpenClaw cron list JSON for safe sharing.
- `receipts_builder.py` — generate a reproducible work receipt (git status/commit/diffstat + commands).
- `runbook_gen.py` — generate a human-readable runbook from OpenClaw cron job JSON.
- `ops_dashboard.py` — generate a simple offline HTML dashboard from local metrics logs.
