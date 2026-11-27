from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from user.models import EmailOTP

User = get_user_model()


class NutritionistRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.email = "dr.priya@example.com"
        self.token = "verified-token-123"
        EmailOTP.objects.create(
            email=self.email,
            otp="123456",
            verification_token=self.token,
            is_verified=True,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def _base_payload(self):
        return {
            "email": self.email,
            "full_name": "Dr. Priya Sharma",
            "phone_number": "9876543210",
            "password": "StrongPassword123!",
            "verification_token": self.token,
            "role": "nutritionist",
            "nutritionist_type": "inhouse",
            "specializations": '["Weight Management", "Diabetes"]',
            "languages_spoken": '["English", "Hindi"]',
            "is_online_available": "true",
            "is_offline_available": "false",
        }

    def test_nutritionist_register_with_db_otp_fallback_and_documents(self):
        # Cache is empty (simulates multi-worker dyno), only EmailOTP DB record exists
        pdf_file = SimpleUploadedFile("degree.pdf", b"%PDF-1.4 fake pdf", content_type="application/pdf")
        payload = self._base_payload()
        payload["qualification_certificate"] = pdf_file

        with patch("utils.cloud.CustomCloudinaryStorage.save", return_value="nutritionist/certificates/degree.pdf") as mock_save:
            res = self.client.post("/api/signup/", payload, format="multipart")
            self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
            mock_save.assert_called_once()
        self.assertTrue(User.objects.filter(email=self.email, role="nutritionist").exists())

    def test_document_upload_failure_rolls_back_user_cleanly(self):
        pdf_file = SimpleUploadedFile("degree.pdf", b"%PDF-1.4 fake pdf", content_type="application/pdf")
        payload = self._base_payload()
        payload["qualification_certificate"] = pdf_file

        with patch("utils.cloud.CustomCloudinaryStorage.save", side_effect=RuntimeError("Cloudinary timeout")):
            res = self.client.post("/api/signup/", payload, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("upload", str(res.data).lower())
        # Atomic rollback: no orphaned User left behind, and EmailOTP still intact for retry
        self.assertFalse(User.objects.filter(email=self.email).exists())
        self.assertTrue(EmailOTP.objects.filter(email=self.email, is_verified=True).exists())

    def test_unsupported_document_extension_rejected_cleanly(self):
        bad_file = SimpleUploadedFile("malware.exe", b"MZ...", content_type="application/octet-stream")
        payload = self._base_payload()
        payload["government_id"] = bad_file

        res = self.client.post("/api/signup/", payload, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("government_id", res.data)
        self.assertFalse(User.objects.filter(email=self.email).exists())

