from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from user.blocking import block_user, unblock_user
from user.models import BlockedContact

User = get_user_model()


class UserBlockingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.email = "blockeduser@gmail.com"
        self.phone = "+91 98765-43210"
        self.password = "SecurePassword123!"
        self.user = User.objects.create_user(
            email=self.email,
            full_name="Blocked User",
            phone_number=self.phone,
            password=self.password,
            role="user",
        )

    def test_block_user_records_email_and_phone_and_prevents_otp_and_signup(self):
        block_user(self.user, reason="Policy violation")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_blocked)
        self.assertFalse(self.user.is_active)

        record = BlockedContact.objects.filter(user=self.user, is_active=True).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.email, "blockeduser@gmail.com")
        self.assertEqual(record.canonical_email, "blockeduser@gmail.com")
        self.assertEqual(record.phone_last10, "9876543210")

        # 1. Exact email blocked at send-otp
        res_otp_exact = self.client.post("/api/send-otp/", {"email": self.email}, format="json")
        self.assertEqual(res_otp_exact.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocked", str(res_otp_exact.data).lower())

        # 2. Gmail dot/+alias evasion blocked at send-otp
        res_otp_alias = self.client.post(
            "/api/send-otp/", {"email": "blocked.user+new@gmail.com"}, format="json"
        )
        self.assertEqual(res_otp_alias.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocked", str(res_otp_alias.data).lower())

        # 3. Different email + same mobile number (different formatting) blocked at send-otp
        res_otp_phone = self.client.post(
            "/api/send-otp/",
            {"email": "freshperson@example.com", "phone_number": "9876543210"},
            format="json",
        )
        self.assertEqual(res_otp_phone.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("blocked", str(res_otp_phone.data).lower())

        # 4. Different email + same mobile number blocked at /api/signup/
        cache.set("verification_token_freshperson@example.com", "tok123", timeout=600)
        res_signup_phone = self.client.post(
            "/api/signup/",
            {
                "email": "freshperson@example.com",
                "full_name": "Fresh Person",
                "phone_number": "09876543210",
                "password": "SecurePassword123!",
                "verification_token": "tok123",
                "role": "user",
            },
            format="json",
        )
        self.assertEqual(res_signup_phone.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocked", str(res_signup_phone.data).lower())

        # 5. Gmail alias + different phone blocked at /api/signup/
        cache.set("verification_token_b.lockeduser+2@gmail.com", "tok456", timeout=600)
        res_signup_alias = self.client.post(
            "/api/signup/",
            {
                "email": "b.lockeduser+2@gmail.com",
                "full_name": "Alias Person",
                "phone_number": "9123456789",
                "password": "SecurePassword123!",
                "verification_token": "tok456",
                "role": "user",
            },
            format="json",
        )
        self.assertEqual(res_signup_alias.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocked", str(res_signup_alias.data).lower())

    def test_blocked_user_cannot_login_or_integration_register(self):
        block_user(self.user, reason="Abuse")

        res_login = self.client.post(
            "/api/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertIn(res_login.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertIn("blocked", str(res_login.data).lower())

        res_int = self.client.post(
            "/api/integration/register/",
            {
                "email": "another@example.com",
                "full_name": "Another",
                "password": "SecurePassword123!",
                "mobile_number": "9876543210",
            },
            format="json",
        )
        self.assertEqual(res_int.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("blocked", str(res_int.data).lower())

    def test_deleting_blocked_user_keeps_contact_blocked_and_unblock_restores(self):
        user2 = User.objects.create_user(
            email="second@gmail.com",
            full_name="Second User",
            phone_number="9988776655",
            password=self.password,
            role="user",
        )
        user2.is_active = False
        user2.save()

        # Deleting the blocked user should preserve BlockedContact
        user2.delete()
        res_otp = self.client.post(
            "/api/send-otp/",
            {"email": "newmail@example.com", "phone_number": "+919988776655"},
            format="json",
        )
        self.assertEqual(res_otp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("blocked", str(res_otp.data).lower())

        # Unblocking user1 allows login again
        block_user(self.user)
        unblock_user(self.user)
        res_login = self.client.post(
            "/api/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)
        self.assertIn("access", res_login.data)

