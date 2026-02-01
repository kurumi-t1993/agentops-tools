import json
import tempfile
import unittest
from pathlib import Path

import regression_harness


class TestRegressionHarness(unittest.TestCase):
    def test_record_and_check(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cases.json"
            p.write_text(json.dumps({"cases": [{"name": "t", "cmd": "echo hi", "expect": ""}]}), encoding="utf-8")
            # record
            rc = regression_harness.main(["--cases", str(p), "--mode", "record"])
            self.assertEqual(rc, 0)
            # check
            rc2 = regression_harness.main(["--cases", str(p), "--mode", "check"])
            self.assertEqual(rc2, 0)


if __name__ == "__main__":
    unittest.main()
