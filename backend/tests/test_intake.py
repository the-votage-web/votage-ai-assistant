import unittest
from app.services.intake.logs import derive_reason


class TestDeriveReason(unittest.TestCase):
    def test_registration_conflict_is_phone_exists(self):
        self.assertEqual(derive_reason("registration", 409), "phone_exists")

    def test_validation(self):
        self.assertEqual(derive_reason("registration", 422), "validation_error")

    def test_server_error(self):
        self.assertEqual(derive_reason("checkin", 500), "server_error")
        self.assertEqual(derive_reason("checkin", 502), "server_error")

    def test_default_ui_error(self):
        self.assertEqual(derive_reason("registration", None), "ui_error")
        self.assertEqual(derive_reason("checkin", 400), "ui_error")


class TestIntakeAdminAuth(unittest.TestCase):
    def _client(self, key="secret-key"):
        from app.db import config
        config.settings.ADMIN_API_KEY = key
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_list_requires_admin(self):
        resp = self._client().get("/api/admin/intake-issues")
        self.assertEqual(resp.status_code, 403)

    def test_list_ok_with_key(self):
        resp = self._client().get("/api/admin/intake-issues",
                                  headers={"X-Admin-Key": "secret-key"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_resolve_missing_is_404(self):
        resp = self._client().patch(
            "/api/admin/intake-issues/00000000-0000-0000-0000-000000000000/resolve",
            headers={"X-Admin-Key": "secret-key"})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
