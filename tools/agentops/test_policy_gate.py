import tempfile
import unittest

import policy_gate


class TestPolicyGate(unittest.TestCase):
    def test_blocks_cmd_pattern(self):
        txt = """
allowed:
  exec: true
blocked_cmd_patterns:
  - "\\bcurl\\b"
"""
        p = policy_gate.parse_policy(txt)
        ok, reason = policy_gate.is_cmd_allowed("curl http://x", p)
        self.assertFalse(ok)
        self.assertIn("blocked", reason)

    def test_write_allowed_prefix(self):
        txt = """
write_paths:
  - ./
"""
        p = policy_gate.parse_policy(txt)
        self.assertTrue(policy_gate.is_write_allowed("./foo.txt", p))


if __name__ == "__main__":
    unittest.main()
