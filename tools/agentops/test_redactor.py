import unittest

from redactor import redact_text


class TestRedactor(unittest.TestCase):
    def test_email(self):
        out, applied = redact_text("contact me at foo.bar+test@example.com")
        self.assertIn("[REDACTED_EMAIL]", out)
        self.assertIn("email", applied)

    def test_uuid(self):
        out, applied = redact_text("uuid=a9beb66a-207e-440d-8d9a-bb47b5e66790")
        self.assertIn("[REDACTED_UUID]", out)
        self.assertIn("uuid", applied)

    def test_mac(self):
        out, applied = redact_text("en0 00:11:22:33:44:55")
        self.assertIn("[REDACTED_MAC]", out)
        self.assertIn("mac", applied)

    def test_lan_ip(self):
        out, applied = redact_text("addr 192.168.3.44")
        self.assertIn("[REDACTED_LAN_IP]", out)
        self.assertIn("lan_ip", applied)

    def test_auth_header(self):
        out, applied = redact_text("Authorization: Bearer abcdef\n")
        self.assertIn("Authorization: [REDACTED_AUTH]", out)
        self.assertIn("auth_header", applied)

    def test_kv_secret(self):
        out, applied = redact_text("api_key=supersecret")
        self.assertIn("api_key=[REDACTED_TOKEN]", out)
        self.assertIn("kv_secrets", applied)


if __name__ == "__main__":
    unittest.main()
