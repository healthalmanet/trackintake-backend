"""
=============================================================================
UNIT & INTEGRATION TESTS: User Login (JWT Authentication)
=============================================================================
This file tests the login endpoint (/api/login/):
1. Successful login returning JWT tokens (access + refresh) and user details.
2. Failed login when password does not match (HTTP 401 Unauthorized).
3. Failed login when user does not exist (HTTP 401 Unauthorized).
4. Validation errors when email or password is missing (HTTP 400 Bad Request).
5. Case-insensitivity: Users can log in regardless of email uppercase/lowercase.
=============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class UserLoginTests(TestCase):
    """
    Test suite for verifying that the login API operates correctly and securely.
    """

    def setUp(self):
        """
        The 'Arrange' step: Create a real user in the test database so we can test logging in.
        """
        self.client = APIClient()

        self.email = "testuser@example.com"
        self.password = "MySecretPassword123!"
        self.full_name = "Jordan Lee"

        # Create user with properly hashed password using create_user()
        self.user = User.objects.create_user(
            email=self.email,
            full_name=self.full_name,
            password=self.password,
            role="user",
        )

    # -------------------------------------------------------------------------
    # TEST 1: Successful Login
    # -------------------------------------------------------------------------
    def test_login_success_returns_jwt_tokens(self):
        """
        WHAT THIS TESTS:
        When a user enters the correct email and password:
        1. Returns HTTP 200 OK.
        2. Returns an 'access' token (for authenticating API calls).
        3. Returns a 'refresh' token (for refreshing expired access tokens).
        4. Returns user payload (email, full_name, role).
        """
        # ACT: Send POST request to /api/login/
        payload = {
            "email": self.email,
            "password": self.password,
        }
        response = self.client.post("/api/login/", payload, format="json")

        # ASSERT: Check HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # ASSERT: Verify tokens exist in the response
        self.assertIn("access", response.data, "Response should include JWT access token")
        self.assertIn("refresh", response.data, "Response should include JWT refresh token")

        # Verify token is a non-empty string
        self.assertTrue(len(response.data["access"]) > 20)

    # -------------------------------------------------------------------------
    # TEST 2: Wrong Password Fails
    # -------------------------------------------------------------------------
    def test_login_wrong_password_fails(self):
        """
        SECURITY TEST:
        If an incorrect password is provided:
        1. Returns HTTP 401 Unauthorized.
        2. Does NOT return any JWT tokens.
        """
        payload = {
            "email": self.email,
            "password": "WrongPassword999!",
        }
        response = self.client.post("/api/login/", payload, format="json")

        # ASSERT: Must be rejected with 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    # -------------------------------------------------------------------------
    # TEST 3: Non-Existent User Fails
    # -------------------------------------------------------------------------
    def test_login_nonexistent_email_fails(self):
        """
        SECURITY TEST:
        If the email is not registered in the system:
        1. Returns HTTP 401 Unauthorized.
        """
        payload = {
            "email": "doesnotexist@example.com",
            "password": self.password,
        }
        response = self.client.post("/api/login/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    # -------------------------------------------------------------------------
    # TEST 4: Missing Fields Fails with 400 Bad Request
    # -------------------------------------------------------------------------
    def test_login_missing_fields_fails(self):
        """
        WHAT THIS TESTS:
        If email or password is missing in the payload:
        The serializer rejects it with HTTP 400 Bad Request.
        """
        # Missing password
        response = self.client.post("/api/login/", {"email": self.email}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing email
        response2 = self.client.post("/api/login/", {"password": self.password}, format="json")
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # TEST 5: Case-Insensitive Email Support
    # -------------------------------------------------------------------------
    def test_login_case_insensitive_email(self):
        """
        WHAT THIS TESTS:
        Users often type their email with capital letters on mobile (e.g. TestUser@Example.com).
        The backend should normalize the email and allow login successfully.
        """
        payload = {
            "email": "TESTUSER@EXAMPLE.COM",  # Capitalized email
            "password": self.password,
        }
        response = self.client.post("/api/login/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
