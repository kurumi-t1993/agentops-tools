import unittest

import signal_uptime_guard as g


class TestSignalUptimeGuard(unittest.TestCase):
    def test_now_format(self):
        s = g.now_jst_iso()
        self.assertIn("T", s)


if __name__ == "__main__":
    unittest.main()
