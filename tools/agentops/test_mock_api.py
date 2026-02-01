import unittest

from mock_api import gen_items


class TestMockAPI(unittest.TestCase):
    def test_gen_items(self):
        items = gen_items(3, seed=1)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].id, "1")


if __name__ == "__main__":
    unittest.main()
