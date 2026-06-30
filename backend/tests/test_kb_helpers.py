import unittest
from app.services.faq.kb import (
    normalize_question,
    parse_existing_questions,
    kb_entry_to_chunk,
    render_faq_markdown,
)


class TestKbHelpers(unittest.TestCase):
    def test_normalize_question_is_case_and_space_insensitive(self):
        self.assertEqual(
            normalize_question("  What  TIME is service? "),
            normalize_question("what time is service"),
        )

    def test_parse_existing_questions_reads_q_lines(self):
        md = "# Source: home\n## Q: What time is service?\nA: 9am\n## Q: Where are you?\nA: Benin"
        found = parse_existing_questions(md)
        self.assertIn(normalize_question("What time is service?"), found)
        self.assertIn(normalize_question("Where are you?"), found)

    def test_kb_entry_to_chunk_shape_and_id(self):
        chunk = kb_entry_to_chunk({"id": "abc-123", "question": "Q1", "answer": "A1"})
        self.assertEqual(chunk["id"], "admin:abc-123")
        self.assertEqual(chunk["question"], "Q1")
        self.assertEqual(chunk["answer"], "A1")
        self.assertEqual(chunk["text"], "Q: Q1\nA: A1")
        self.assertEqual(chunk["source"], "admin")

    def test_render_appends_new_entries_under_admin_source(self):
        seed = "# Source: home\n## Q: What time is service?\nA: 9am"
        out = render_faq_markdown(seed, [{"id": "1", "question": "Do you allow pets?", "answer": "Service animals welcome."}])
        self.assertIn("# Source: admin", out)
        self.assertIn("## Q: Do you allow pets?", out)
        self.assertIn("A: Service animals welcome.", out)
        self.assertTrue(out.startswith(seed.rstrip()))

    def test_render_dedups_questions_already_in_seed(self):
        seed = "# Source: home\n## Q: What time is service?\nA: 9am"
        out = render_faq_markdown(seed, [{"id": "1", "question": "what TIME is service?", "answer": "different"}])
        self.assertEqual(out.count("## Q: "), 1)  # no duplicate question added


from app.services.faq.kb import _validate_fields, MAX_FIELD_LEN  # noqa: E402


class TestKbValidation(unittest.TestCase):
    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            _validate_fields("  ", "answer")
        with self.assertRaises(ValueError):
            _validate_fields("question", "")

    def test_rejects_too_long(self):
        with self.assertRaises(ValueError):
            _validate_fields("q", "a" * (MAX_FIELD_LEN + 1))

    def test_accepts_and_strips(self):
        q, a = _validate_fields("  hi  ", "  there  ")
        self.assertEqual((q, a), ("hi", "there"))


if __name__ == "__main__":
    unittest.main()
