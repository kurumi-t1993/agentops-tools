import unittest

from secrets_scan import scan_text, load_allowlist


class TestSecretsScan(unittest.TestCase):
    def test_detect_github_pat(self):
        allow = []
        text = "token=ghp_" + "a" * 30
        findings = scan_text(text, path="x", allowlist=allow)
        self.assertTrue(any(f.kind == "github_pat" for f in findings))

    def test_allowlist(self):
        # allowlist regex should suppress
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(r"ghp_\\w+\n")
            p = f.name
        allow = load_allowlist(p)
        text = "ghp_" + "a" * 30
        findings = scan_text(text, path="x", allowlist=allow)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
