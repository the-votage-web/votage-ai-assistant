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


if __name__ == "__main__":
    unittest.main()
