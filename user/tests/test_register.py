"""
=============================================================================
UNIT & INTEGRATION TESTS: User Registration & OTP Verification
=============================================================================
This file tests the complete registration flow:
1. Sending an OTP to the user's email.
2. Verifying the OTP and receiving a secure verification token.
3. Submitting the registration form with email, password, full name, and token.
4. Verifying security checks (preventing signup without verification, duplicate emails).
=============================================================================
"""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

# Get the custom User model configured in project settings
User = get_user_model()


class UserRegistrationTests(TestCase):
    """
    TestCase handles database setup and teardown automatically.
    Every test method inside this class runs in its own database transaction,
    meaning any created data is automatically wiped clean after the test finishes.
    """

    def setUp(self):
        """
        The setUp() method runs BEFORE every individual test method.
        We use it to prepare the API client and test data (The 'Arrange' step).
        """
        # APIClient simulates HTTP requests (like Postman or a browser)
        self.client = APIClient()

        # Dummy user details for testing registration
        self.test_email = "newuser@example.com"
        self.test_password = "SecurePassword123!"
        self.test_name = "Alex Johnson"

        # Clear cache before each test to ensure no leftovers from previous tests
        cache.clear()

    # -------------------------------------------------------------------------
    # TEST 1: Sending an OTP (One-Time Password) to user's email
    # -------------------------------------------------------------------------
    @patch("utils.resend_email.send_resend_email")
    def test_send_otp_success(self, mock_email):
        """
        WHAT THIS TESTS:
        When a user enters their email on the signup screen, the system should:
        1. Generate a 6-digit OTP.
        2. Store it in cache (for 10 minutes).
        3. Send the OTP via email (mocked here so we don't send real emails).
        4. Return HTTP 200 OK.
        """
        # ACT: Make a POST request to /api/send-otp/
        response = self.client.post("/api/send-otp/", {"email": self.test_email}, format="json")

        # ASSERT: Check that the API returned 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("message"), "OTP sent.")

        # ASSERT: Verify that the OTP was saved into the cache for this email
        cached_otp = cache.get(f"otp_{self.test_email}")
        self.assertIsNotNone(cached_otp, "OTP should be stored in Django cache")
        self.assertEqual(len(cached_otp), 6, "OTP should be a 6-digit code")

        # ASSERT: Verify that our email sender was called once
        mock_email.assert_called_once()

    # -------------------------------------------------------------------------
    # TEST 2: Verifying the OTP and receiving a verification token
    # -------------------------------------------------------------------------
    def test_verify_otp_success(self):
        """
        WHAT THIS TESTS:
        When the user enters the correct 6-digit code:
        1. The system checks the code against cache.
        2. If it matches, the system issues a secure 'verification_token'.
        3. The token is saved in cache so the signup endpoint can verify it later.
        """
        # ARRANGE: Pre-store a known OTP in cache
        correct_otp = "123456"
        cache.set(f"otp_{self.test_email}", correct_otp, timeout=600)

        # ACT: Call /api/verify-otp/ with the correct email and code
        payload = {"email": self.test_email, "otp": correct_otp}
        response = self.client.post("/api/verify-otp/", payload, format="json")

        # ASSERT: Expect HTTP 200 OK and a verification token returned in response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("verification_token", response.data)

        # ASSERT: Verify the token exists in cache
        token = response.data["verification_token"]
        cached_token = cache.get(f"verification_token_{self.test_email}")
        self.assertEqual(token, cached_token)

    # -------------------------------------------------------------------------
    # TEST 3: Verifying with wrong OTP fails
    # -------------------------------------------------------------------------
    def test_verify_otp_invalid_code_fails(self):
        """
        WHAT THIS TESTS:
        If the user enters the wrong code (e.g. '000000' instead of '123456'),
        the system must reject it with HTTP 400 Bad Request.
        """
        # ARRANGE: Set correct OTP in cache
        cache.set(f"otp_{self.test_email}", "123456", timeout=600)

        # ACT: Submit incorrect OTP
        payload = {"email": self.test_email, "otp": "999999"}
        response = self.client.post("/api/verify-otp/", payload, format="json")

        # ASSERT: Check that the request was rejected
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    # -------------------------------------------------------------------------
    # TEST 4: Successful User Registration
    # -------------------------------------------------------------------------
    def test_register_user_success(self):
        """
        WHAT THIS TESTS:
        When user submits registration data with a valid verification token:
        1. A new User row is created in the database.
        2. The password is encrypted/hashed (not stored as plain text).
        3. The role defaults to 'user'.
        4. The verification token is removed from cache (cannot be reused).
        5. Returns HTTP 201 Created.
        """
        # ARRANGE: Simulate that email verification was already completed
        valid_token = "valid_secure_token_abc_123"
        cache.set(f"verification_token_{self.test_email}", valid_token, timeout=600)

        # ACT: Call the registration endpoint
        payload = {
            "email": self.test_email,
            "full_name": self.test_name,
            "password": self.test_password,
            "verification_token": valid_token,
            "role": "user",
        }
        response = self.client.post("/api/signup/", payload, format="json")

        # ASSERT: Status should be 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get("message"), "Registration successful. Please log in.")

        # ASSERT: Check the User model in the database
        user = User.objects.filter(email=self.test_email).first()
        self.assertIsNotNone(user, "User should exist in the database")
        self.assertEqual(user.full_name, self.test_name)
        self.assertEqual(user.role, "user")

        # ASSERT: Password must be securely hashed, never stored as plain text
        self.assertTrue(user.check_password(self.test_password))
        self.assertNotEqual(user.password, self.test_password)

        # ASSERT: Verification token must be cleared so it cannot be used again
        self.assertIsNone(cache.get(f"verification_token_{self.test_email}"))

    # -------------------------------------------------------------------------
    # TEST 5: Registration without verification token is blocked
    # -------------------------------------------------------------------------
    def test_register_without_valid_token_blocked(self):
        """
        SECURITY TEST:
        If an attacker bypasses the OTP step and directly calls /api/signup/
        with a fake token or missing token, the server must block registration.
        """
        payload = {
            "email": self.test_email,
            "full_name": self.test_name,
            "password": self.test_password,
            "verification_token": "fake_unverified_token",
        }
        response = self.client.post("/api/signup/", payload, format="json")

        # ASSERT: Expect HTTP 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or expired verification token", response.data.get("message", ""))

        # ASSERT: Ensure no user was created in the database
        self.assertFalse(User.objects.filter(email=self.test_email).exists())

    # -------------------------------------------------------------------------
    # TEST 6: Registering with an already existing email is blocked
    # -------------------------------------------------------------------------
    def test_register_duplicate_email_fails(self):
        """
        WHAT THIS TESTS:
        If a user with this email already exists, registration must be rejected
        with a clear error message that the email is already in use.
        """
        # ARRANGE: Create an existing user first
        User.objects.create_user(
            email=self.test_email,
            full_name="Existing User",
            password="ExistingPassword123",
            role="user"
        )

        # Set up a verification token for the duplicate email
        valid_token = "token_for_dup_test"
        cache.set(f"verification_token_{self.test_email}", valid_token, timeout=600)

        # ACT: Try to register again with the same email
        payload = {
            "email": self.test_email,
            "full_name": "Second User",
            "password": "SecondPassword123",
            "verification_token": valid_token,
        }
        response = self.client.post("/api/signup/", payload, format="json")

        # ASSERT: Expect HTTP 400 Bad Request because email is unique
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
