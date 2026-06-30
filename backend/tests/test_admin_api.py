import unittest
from unittest.mock import MagicMock


class TestFaqServiceLiveEdits(unittest.TestCase):
    def _service(self):
        from app.services.faq.faq import faq_service
        faq_service.embedder = MagicMock()
        faq_service.embedder.embed.return_value = [0.0] * 1536
        faq_service.retriever = MagicMock()
        return faq_service

    def test_add_entry_appends_live_chunk(self):
        svc = self._service()
        before = len(svc._faq_chunks)
        svc.add_entry({"id": "test-xyz", "question": "Test only Q?", "answer": "Test only A."})
        ids = [c["id"] for c in svc._faq_chunks]
        self.assertIn("admin:test-xyz", ids)
        svc.retriever.upsert_vector.assert_called_once()
        # cleanup so the singleton isn't polluted for other tests
        svc.remove_entry("test-xyz")
        self.assertEqual(len(svc._faq_chunks), before)


if __name__ == "__main__":
    unittest.main()
