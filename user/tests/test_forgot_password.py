"""
=============================================================================
UNIT & INTEGRATION TESTS: Forgot Password & Reset Password Flow
=============================================================================
This file tests the password recovery workflow:
1. User requests a password reset link via /api/forgot-password/
2. System generates a secure one-time token and sends a reset email.
3. User visits the reset link and submits /api/reset-password/ with:
   - uidb64: Base64-encoded User ID
   - token: Django's cryptographic PasswordResetTokenGenerator token
   - new_password: The user's new password
4. Security tests: Tampered token, invalid UID, non-existent user handling.
=============================================================================
"""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class ForgotAndResetPasswordTests(TestCase):
    """
    Test suite for password recovery and reset functionalities.
    """

    def setUp(self):
        """
        The 'Arrange' step: Create an existing user who will test resetting their password.
        """
        self.client = APIClient()

        self.email = "forgot_test@example.com"
        self.old_password = "OldPassword123!"
        self.new_password = "BrandNewPassword2026!"

        self.user = User.objects.create_user(
            email=self.email,
            full_name="Sam Taylor",
            password=self.old_password,
            role="user",
        )

    # -------------------------------------------------------------------------
    # TEST 1: Requesting a Password Reset Email
    # -------------------------------------------------------------------------
    @patch("user.views.send_resend_email")
    def test_forgot_password_request_success(self, mock_email_sender):
        """
        WHAT THIS TESTS:
        When a registered user enters their email:
        1. System finds the user.
        2. Generates a uidb64 and a cryptographic reset token.
        3. Sends an email with the link (mocked here so no real emails are sent).
        4. Returns HTTP 200 OK.
        """
        # ACT: Call /api/forgot-password/
        response = self.client.post("/api/forgot-password/", {"email": self.email}, format="json")

        # ASSERT: Expect HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Password reset link has been sent", response.data.get("message", ""))

        # ASSERT: Verify that the email utility was invoked with the user's email
        mock_email_sender.assert_called_once()
        call_kwargs = mock_email_sender.call_args[1]
        self.assertEqual(call_kwargs["to"], self.email)

    # -------------------------------------------------------------------------
    # TEST 2: Forgot Password for Non-Existent Email (Security Check)
    # -------------------------------------------------------------------------
    @patch("user.views.send_resend_email")
    def test_forgot_password_nonexistent_email_does_not_reveal_user(self, mock_email_sender):
        """
        SECURITY TEST (Account Enumeration Prevention):
        If an attacker enters an email that does NOT exist:
        The system still returns HTTP 200 OK with a generic message,
        so the attacker cannot guess which emails are registered on the platform.
        No email should be sent.
        """
        response = self.client.post(
            "/api/forgot-password/",
            {"email": "nobody_here@example.com"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Email sender should NOT be called for a non-existent email
        mock_email_sender.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST 3: Successfully Resetting Password with Valid Token
    # -------------------------------------------------------------------------
    def test_reset_password_success(self):
        """
        WHAT THIS TESTS:
        When the user clicks the reset link in their email:
        1. The frontend extracts uidb64 and token from the URL.
        2. The user types their new password.
        3. The backend verifies the token is valid for this user.
        4. The password in the database is changed to the new password.
        5. The user can now log in using the new password, and old password stops working.
        """
        # ARRANGE: Generate the valid uidb64 and token like Django does
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = PasswordResetTokenGenerator().make_token(self.user)

        # ACT: Call /api/reset-password/
        payload = {
            "uidb64": uidb64,
            "token": token,
            "new_password": self.new_password,
        }
        response = self.client.post("/api/reset-password/", payload, format="json")

        # ASSERT: Check HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Password has been reset successfully", response.data.get("message", ""))

        # ASSERT: Reload user from DB and verify old password fails and new password works
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.old_password), "Old password should no longer work")
        self.assertTrue(self.user.check_password(self.new_password), "New password should now work")

    # -------------------------------------------------------------------------
    # TEST 4: Resetting with an Invalid or Expired Token Fails
    # -------------------------------------------------------------------------
    def test_reset_password_invalid_token_fails(self):
        """
        SECURITY TEST:
        If a user tampers with the token or uses an expired token:
        1. Returns HTTP 400 Bad Request.
        2. The password is NOT modified.
        """
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        fake_token = "invalid-or-expired-token-12345"

        payload = {
            "uidb64": uidb64,
            "token": fake_token,
            "new_password": self.new_password,
        }
        response = self.client.post("/api/reset-password/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or expired token", response.data.get("error", ""))

        # Password remains unchanged
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    # -------------------------------------------------------------------------
    # TEST 5: Resetting with an Invalid UID Fails
    # -------------------------------------------------------------------------
    def test_reset_password_invalid_uid_fails(self):
        """
        SECURITY TEST:
        If the uidb64 string is corrupted or points to a non-existent user:
        The server rejects it with HTTP 400 Bad Request.
        """
        payload = {
            "uidb64": "invalid_uid_string",
            "token": "some-token",
            "new_password": self.new_password,
        }
        response = self.client.post("/api/reset-password/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or expired link", response.data.get("error", ""))
