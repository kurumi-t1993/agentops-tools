import os
import tempfile
import unittest
from pathlib import Path

from metrics_snapshot import redact_block


class TestMetricsSnapshot(unittest.TestCase):
    def test_redact_block(self):
        s = "mac 00:11:22:33:44:55 ip 192.168.1.2 email foo@example.com"
        out = redact_block(s)
        self.assertIn("[REDACTED_MAC]", out)
        self.assertIn("[REDACTED_LAN_IP]", out)
        self.assertIn("[REDACTED_EMAIL]", out)


if __name__ == "__main__":
    unittest.main()
