# AgentOps Tools (offline-first)

This folder contains local-first utilities to make agent workflows safer and more reliable.

## Tools

- `redactor.py` — redact secrets/PII from text/logs.
- `cron_lint.py` — lint and simulate cron/interval schedules for OpenClaw-style job JSON.

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
echo 'Authorization: Bearer abcdef1234567890' | python3 redactor.py
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
