import tempfile
import unittest
from pathlib import Path

import ops_dashboard


class TestOpsDashboard(unittest.TestCase):
    def test_extract_snapshots(self):
        md = "## Snapshot @ 2026-02-01 01:02:36 JST\n"
        snaps = ops_dashboard.extract_snapshots(md)
        self.assertEqual(snaps, ["2026-02-01 01:02:36 JST"])

    def test_generate_html(self):
        with tempfile.TemporaryDirectory() as d:
            md_dir = Path(d)
            (md_dir / "signal-uptime.log").write_text("x\n", encoding="utf-8")
            (md_dir / "2026-02-01.metrics.md").write_text("## Snapshot @ t\n", encoding="utf-8")
            out = md_dir / "dash.html"
            ops_dashboard.main(["--metrics-dir", str(md_dir), "--out", str(out), "--days", "1", "--uptime-lines", "10"])
            self.assertTrue(out.exists())
            self.assertIn("AgentOps Dashboard", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
