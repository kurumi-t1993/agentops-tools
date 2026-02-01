import json
import tempfile
import unittest
from pathlib import Path

import audit_report


class TestAuditReport(unittest.TestCase):
    def test_diff(self):
        prev = {"jobs": [{"id": "1", "name": "a", "enabled": True, "schedule": {"kind": "every", "everyMs": 1}, "payload": {"kind": "agentTurn", "timeoutSeconds": 1}}]}
        cur = {"jobs": [{"id": "1", "name": "a", "enabled": False, "schedule": {"kind": "every", "everyMs": 1}, "payload": {"kind": "agentTurn", "timeoutSeconds": 1}},
                        {"id": "2", "name": "b", "enabled": True, "schedule": {"kind": "cron", "expr": "0 8 * * *"}, "payload": {"kind": "agentTurn", "timeoutSeconds": 2}}]}
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p1 = d / "prev.json"; p1.write_text(json.dumps(prev), encoding="utf-8")
            p2 = d / "cur.json"; p2.write_text(json.dumps(cur), encoding="utf-8")
            out = d / "out.md"
            rc = audit_report.main(["--current", str(p2), "--previous", str(p1), "--out", str(out)])
            self.assertEqual(rc, 0)
            t = out.read_text(encoding="utf-8")
            self.assertIn("Added:", t)
            self.assertIn("Changed", t)


if __name__ == "__main__":
    unittest.main()
