"""
=============================================================================
END-TO-END AUTHENTICATION LIFECYCLE INTEGRATION TEST
=============================================================================
This test executes the complete user journey from start to finish:
Step 1: Request OTP for email verification
Step 2: Submit OTP and receive secure verification token
Step 3: Register a new account with the token
Step 4: Log in with the registered credentials to receive JWT tokens
Step 5: Trigger a 'Forgot Password' request
Step 6: Reset the password using the generated token
Step 7: Confirm the OLD password is rejected (401 Unauthorized)
Step 8: Confirm the NEW password works and logs in successfully (200 OK)
=============================================================================
"""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class EndToEndAuthLifecycleTests(TestCase):
    """
    Simulates a full end-to-end user lifecycle across all authentication endpoints.
    """

    def setUp(self):
        self.client = APIClient()
        self.email = "e2e_user@example.com"
        self.initial_password = "FirstPassword123!"
        self.updated_password = "SecondPassword456!"
        self.full_name = "Morgan Rivera"
        cache.clear()

    @patch("utils.resend_email.send_resend_email")
    @patch("user.views.send_resend_email")
    def test_complete_registration_login_and_password_reset_journey(
        self, mock_user_email, mock_utils_email
    ):
        """
        Executes all 8 steps of the authentication lifecycle in a single connected journey.
        """

        # ---------------------------------------------------------------------
        # STEP 1: Request an OTP to verify email
        # ---------------------------------------------------------------------
        otp_resp = self.client.post("/api/send-otp/", {"email": self.email}, format="json")
        self.assertEqual(otp_resp.status_code, status.HTTP_200_OK)

        # Retrieve the generated OTP stored in the server's cache
        generated_otp = cache.get(f"otp_{self.email}")
        self.assertIsNotNone(generated_otp, "OTP must be saved in cache")

        # ---------------------------------------------------------------------
        # STEP 2: Verify the OTP and receive a verification token
        # ---------------------------------------------------------------------
        verify_resp = self.client.post(
            "/api/verify-otp/",
            {"email": self.email, "otp": generated_otp},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        verification_token = verify_resp.data.get("verification_token")
        self.assertIsNotNone(verification_token, "Must receive a verification token")

        # ---------------------------------------------------------------------
        # STEP 3: Complete Account Registration
        # ---------------------------------------------------------------------
        signup_payload = {
            "email": self.email,
            "full_name": self.full_name,
            "password": self.initial_password,
            "verification_token": verification_token,
            "role": "user",
        }
        signup_resp = self.client.post("/api/signup/", signup_payload, format="json")
        self.assertEqual(signup_resp.status_code, status.HTTP_201_CREATED)

        # Confirm user exists in the database
        user = User.objects.get(email=self.email)
        self.assertEqual(user.full_name, self.full_name)

        # ---------------------------------------------------------------------
        # STEP 4: Log in with credentials and obtain JWT tokens
        # ---------------------------------------------------------------------
        login_resp = self.client.post(
            "/api/login/",
            {"email": self.email, "password": self.initial_password},
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_resp.data)
        self.assertIn("refresh", login_resp.data)

        # ---------------------------------------------------------------------
        # STEP 5: Request Forgot Password Link
        # ---------------------------------------------------------------------
        forgot_resp = self.client.post(
            "/api/forgot-password/",
            {"email": self.email},
            format="json",
        )
        self.assertEqual(forgot_resp.status_code, status.HTTP_200_OK)

        # ---------------------------------------------------------------------
        # STEP 6: Reset Password with Reset Token
        # ---------------------------------------------------------------------
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        reset_token = PasswordResetTokenGenerator().make_token(user)

        reset_resp = self.client.post(
            "/api/reset-password/",
            {
                "uidb64": uidb64,
                "token": reset_token,
                "new_password": self.updated_password,
            },
            format="json",
        )
        self.assertEqual(reset_resp.status_code, status.HTTP_200_OK)

        # ---------------------------------------------------------------------
        # STEP 7: Verify Old Password is REJECTED
        # ---------------------------------------------------------------------
        old_login_resp = self.client.post(
            "/api/login/",
            {"email": self.email, "password": self.initial_password},
            format="json",
        )
        self.assertEqual(
            old_login_resp.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Old password must no longer be accepted",
        )

        # ---------------------------------------------------------------------
        # STEP 8: Verify New Password SUCCEEDS
        # ---------------------------------------------------------------------
        new_login_resp = self.client.post(
            "/api/login/",
            {"email": self.email, "password": self.updated_password},
            format="json",
        )
        self.assertEqual(
            new_login_resp.status_code,
            status.HTTP_200_OK,
            "New password must successfully log the user in",
        )
        self.assertIn("access", new_login_resp.data)
