from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from appointments.models import Appointment, AvailabilitySlot
from nutritionist.models import NutritionistProfile

User = get_user_model()


class AppointmentCancelTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.patient = User.objects.create_user(
            email="patient_cancel@example.com",
            full_name="Patient Cancel",
            password="testpassword123",
            role="user",
        )
        self.other_user = User.objects.create_user(
            email="other_user@example.com",
            full_name="Other User",
            password="testpassword123",
            role="user",
        )
        self.nutritionist = User.objects.create_user(
            email="nutri_cancel@example.com",
            full_name="Dr. Nutri Cancel",
            password="testpassword123",
            role="nutritionist",
        )
        self.nutri_profile = self.nutritionist.nutritionist_profile
        self.nutri_profile.online_price = 750.00
        self.nutri_profile.save()

        # Dates
        self.future_date = timezone.localdate() + timedelta(days=5)

        # Slot
        self.slot = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.future_date,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type="VIRTUAL",
            is_booked=True,
        )

        # Appointment
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            nutritionist=self.nutritionist,
            slot=self.slot,
            slot_date=self.slot.date,
            slot_start_time=self.slot.start_time,
            slot_end_time=self.slot.end_time,
            appointment_category="IN_HOUSE",
            appointment_type="VIRTUAL",
            assigned_by="SYSTEM",
            status="CONFIRMED",
            fee_amount=750.00,
            payment_status="PAID",
        )

    @patch("appointments.views.send_cancellation_emails")
    def test_cancel_by_patient_more_than_24h_eligible_for_refund(self, mock_email):
        """Cancelling >24h prior: slot is freed, status CANCELLED, payment PENDING_REFUND."""
        self.client.force_authenticate(user=self.patient)

        url = f"/api/appointments/{self.appointment.id}/cancel/"
        reason = "Traveling out of town"
        response = self.client.post(url, {"reason": reason}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("cancelled successfully", response.data.get("detail", ""))

        # Check slot freed
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.is_booked)

        # Check appointment status and refund
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "CANCELLED")
        self.assertEqual(self.appointment.cancelled_by, "PATIENT")
        self.assertEqual(self.appointment.cancellation_reason, reason)
        self.assertEqual(self.appointment.payment_status, "PENDING_REFUND")
        self.assertEqual(float(self.appointment.refund_amount), 750.00)
        self.assertEqual(self.appointment.payout_status, "CANCELLED")

        # Check email call
        mock_email.assert_called_once()

    @patch("appointments.views.send_cancellation_emails")
    def test_cancel_by_patient_within_24h_no_refund(self, mock_email):
        """Cancelling within 24h: slot is freed, status CANCELLED, payment NO_REFUND."""
        # Set timing to 3 hours in the future in active timezone
        near_time = timezone.localtime() + timedelta(hours=3)
        self.appointment.slot_date = near_time.date()
        self.appointment.slot_start_time = near_time.time().replace(microsecond=0)
        self.appointment.save()

        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/cancel/"
        response = self.client.post(url, {"reason": "Sudden emergency"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.slot.refresh_from_db()
        self.assertFalse(self.slot.is_booked)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "CANCELLED")
        self.assertEqual(self.appointment.cancelled_by, "PATIENT")
        self.assertEqual(self.appointment.payment_status, "NO_REFUND")

    @patch("appointments.views.send_cancellation_emails")
    def test_cancel_by_nutritionist_eligible_for_patient_refund(self, mock_email):
        """
        When a nutritionist cancels an appointment that was paid for,
        the patient is 100% eligible for a refund:
        - Slot is freed immediately
        - Status is CANCELLED with cancelled_by = NUTRITIONIST
        - payment_status becomes PENDING_REFUND with full refund_amount
        """
        self.client.force_authenticate(user=self.nutritionist)

        url = f"/api/appointments/{self.appointment.id}/cancel/"
        response = self.client.post(url, {"reason": "Doctor unwell"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.slot.refresh_from_db()
        self.assertFalse(self.slot.is_booked)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "CANCELLED")
        self.assertEqual(self.appointment.cancelled_by, "NUTRITIONIST")
        # Patient is eligible for full refund of the fee paid (750.00)
        self.assertEqual(self.appointment.payment_status, "PENDING_REFUND")
        self.assertEqual(self.appointment.refund_amount, Decimal("750.00"))

    def test_cannot_cancel_already_cancelled_appointment(self):
        """Attempting to cancel an already cancelled appointment returns 400."""
        self.appointment.status = "CANCELLED"
        self.appointment.save()

        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/cancel/"
        response = self.client.post(url, {"reason": "Cancel again"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been cancelled", response.data.get("detail", ""))

    def test_cannot_cancel_past_appointment(self):
        """Attempting to cancel a past appointment returns 400."""
        past_time = timezone.now() - timedelta(hours=2)
        self.appointment.slot_date = past_time.date()
        self.appointment.slot_start_time = past_time.time()
        self.appointment.save()

        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/cancel/"
        response = self.client.post(url, {"reason": "Missed it"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already started or passed", response.data.get("detail", ""))

    def test_unauthorized_user_cannot_cancel(self):
        """An arbitrary user cannot cancel another patient's appointment."""
        self.client.force_authenticate(user=self.other_user)
        url = f"/api/appointments/{self.appointment.id}/cancel/"
        response = self.client.post(url, {"reason": "Malicious cancel"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
