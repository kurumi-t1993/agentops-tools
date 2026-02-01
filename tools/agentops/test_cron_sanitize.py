import json
import tempfile
import unittest

from cron_sanitize import redact_obj


class TestCronSanitize(unittest.TestCase):
    def test_redacts_home_and_uuid(self):
        obj = {
            "jobs": [
                {
                    "payload": {
                        "message": "path /Users/day/.openclaw/workspace and uuid a9beb66a-207e-440d-8d9a-bb47b5e66790"
                    }
                }
            ]
        }
        out = redact_obj(obj)
        msg = out["jobs"][0]["payload"]["message"]
        self.assertIn("/Users/[REDACTED_USER]/", msg)
        self.assertIn("[REDACTED_UUID]", msg)


if __name__ == "__main__":
    unittest.main()
