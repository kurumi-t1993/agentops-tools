import unittest
from datetime import datetime, timedelta

from cron_lint import parse_cron, next_cron_times, tzinfo_from_name, simulate_job, lint_job


class TestCronLint(unittest.TestCase):
    def test_parse_cron_basic(self):
        c = parse_cron("0 8 * * *")
        self.assertIn(0, c.minute)
        self.assertIn(8, c.hour)

    def test_next_cron_times(self):
        tz = tzinfo_from_name("Asia/Tokyo")
        start = datetime(2026, 2, 1, 7, 59, tzinfo=tz)
        c = parse_cron("0 8 * * *")
        times = next_cron_times(start, c, timedelta(hours=2))
        self.assertTrue(any(t.hour == 8 and t.minute == 0 for t in times))

    def test_sim_every(self):
        tz = tzinfo_from_name("Asia/Tokyo")
        now = datetime(2026, 2, 1, 8, 0, tzinfo=tz)
        job = {"schedule": {"kind": "every", "everyMs": 60_000, "anchorMs": int(now.timestamp() * 1000)}}
        times = simulate_job(job, now=now, horizon=timedelta(minutes=3), tz=tz)
        self.assertEqual(len(times), 3)

    def test_lint_timeout_missing(self):
        job = {"id": "1", "name": "x", "schedule": {"kind": "every", "everyMs": 900000}, "payload": {"kind": "agentTurn", "message": "hi"}}
        findings = lint_job(job)
        self.assertTrue(any(f.level == "WARN" and "timeoutSeconds" in f.message for f in findings))


if __name__ == "__main__":
    unittest.main()
