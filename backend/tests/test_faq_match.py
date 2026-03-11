import unittest

from app.ai.agent import _answer_from_markdown_preferred


class TestFaqMatch(unittest.TestCase):
    def test_rev_ohis_match(self):
        q = "What should I know about Rev. Ohis Ojeikere?"
        a = _answer_from_markdown_preferred(q)
        self.assertIsNotNone(a)
        self.assertIn("Rev. Ohis Ojeikere", a)

    def test_lead_pastors_match(self):
        q = "Who are your lead pastors?"
        a = _answer_from_markdown_preferred(q)
        self.assertIsNotNone(a)
        self.assertIn("Our lead pastors are Rev. Ohis and Pastor Anwinli Ojeikere", a)

    def test_connect_match(self):
        q = "what do you know about connect?"
        a = _answer_from_markdown_preferred(q)
        self.assertIsNotNone(a)
        self.assertIn("connect", a.lower())

    def test_service_time_match(self):
        q = "what time are your services?"
        a = _answer_from_markdown_preferred(q)
        self.assertIsNotNone(a)
        self.assertIn("Service", a)


if __name__ == "__main__":
    unittest.main()
