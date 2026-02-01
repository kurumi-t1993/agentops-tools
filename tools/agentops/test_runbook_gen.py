import json
import tempfile
import unittest


class TestRunbookGen(unittest.TestCase):
    def test_generate(self):
        import runbook_gen
        data = {"jobs": [{"id": "1", "name": "job", "enabled": True, "schedule": {"kind": "every", "everyMs": 60000}, "payload": {"kind": "agentTurn", "timeoutSeconds": 5, "message": "TZ=Asia/Tokyo"}}]}
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump(data, f)
            inp = f.name
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            outp = f.name
        runbook_gen.main(["--in", inp, "--out", outp])
        with open(outp, "r", encoding="utf-8") as rf:
            txt = rf.read()
        self.assertIn("AgentOps Runbook", txt)
        self.assertIn("job", txt)


if __name__ == "__main__":
    unittest.main()
