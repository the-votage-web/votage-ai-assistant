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


class TestAdminAuth(unittest.TestCase):
    def _client(self, key="secret-key"):
        from app.db import config
        config.settings.ADMIN_API_KEY = key
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_login_rejects_wrong_password(self):
        client = self._client()
        resp = client.post("/api/admin/login", json={"password": "nope"})
        self.assertEqual(resp.status_code, 403)

    def test_login_accepts_correct_password(self):
        client = self._client()
        resp = client.post("/api/admin/login", json={"password": "secret-key"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_logs_requires_admin_header(self):
        client = self._client()
        resp = client.get("/api/admin/logs")
        self.assertEqual(resp.status_code, 403)

    def test_kb_create_validates_empty(self):
        client = self._client()
        resp = client.post("/api/admin/kb", json={"question": "", "answer": ""},
                           headers={"X-Admin-Key": "secret-key"})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
