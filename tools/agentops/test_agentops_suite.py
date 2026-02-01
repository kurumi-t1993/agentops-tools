import unittest


class TestAgentopsSuite(unittest.TestCase):
    def test_import(self):
        import agentops_suite
        self.assertTrue(callable(agentops_suite.main))


if __name__ == "__main__":
    unittest.main()
