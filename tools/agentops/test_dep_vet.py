import unittest

from dep_vet import vet_pypi


class TestDepVet(unittest.TestCase):
    def test_vet_pypi_basic(self):
        meta = {
            "info": {"version": "1.0.0", "license": "MIT", "project_urls": {"Homepage": "https://x"}},
            "releases": {"1.0.0": [{"upload_time_iso_8601": "2026-01-01T00:00:00Z", "yanked": False}]},
        }
        res = vet_pypi(meta, "example")
        self.assertTrue(0 <= res.score <= 100)


if __name__ == "__main__":
    unittest.main()
