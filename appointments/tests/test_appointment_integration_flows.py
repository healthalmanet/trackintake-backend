from datetime import time, timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from appointments.models import Appointment, AvailabilitySlot
from nutritionist.models import NutritionistProfile

User = get_user_model()


class AppointmentLifecycleIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.patient = User.objects.create_user(
            email="flow_patient@example.com",
            full_name="Flow Patient",
            password="testpassword123",
            role="user",
        )

        self.nutritionist = User.objects.create_user(
            email="flow_nutri@example.com",
            full_name="Dr. Flow Nutri",
            password="testpassword123",
            role="nutritionist",
        )
        self.profile = self.nutritionist.nutritionist_profile
        self.profile.online_price = 0.00
        self.profile.save()

        self.day1 = timezone.localdate() + timedelta(days=3)
        self.day2 = timezone.localdate() + timedelta(days=5)

        self.slot1 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.day1,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type="BOTH",
            is_booked=False,
        )

        self.slot2 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.day2,
            start_time=time(14, 0),
            end_time=time(14, 30),
            slot_type="BOTH",
            is_booked=False,
        )

    @patch("appointments.serializers.send_booking_confirmation_emails")
    @patch("appointments.serializers.create_zoom_meeting")
    @patch("appointments.views.create_zoom_meeting")
    @patch("appointments.views.send_reschedule_emails")
    @patch("appointments.views.send_cancellation_emails")
    def test_full_appointment_reschedule_and_cancel_lifecycle(
        self, mock_cancel_email, mock_reschedule_email, mock_reschedule_zoom, mock_book_zoom, mock_booking_email
    ):
        """
        Complete end-to-end lifecycle flow:
        1. Patient books slot 1
        2. Patient verifies appointment in 'my appointments'
        3. Patient reschedules to slot 2 (slot 1 freed, slot 2 booked)
        4. Patient cancels appointment (slot 2 freed, status CANCELLED)
        5. Verify final slot availabilities
        """
        mock_book_zoom.return_value = {"join_url": "https://zoom.us/j/lifecycle-initial"}
        mock_reschedule_zoom.return_value = {"join_url": "https://zoom.us/j/lifecycle-rescheduled"}

        self.client.force_authenticate(user=self.patient)

        # ----------------------------------------------------
        # 1. Book appointment on Slot 1
        # ----------------------------------------------------
        book_res = self.client.post("/api/appointments/book/", {
            "slot_id": self.slot1.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        }, format="json")
        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED)
        appointment_id = book_res.data["id"]

        self.slot1.refresh_from_db()
        self.assertTrue(self.slot1.is_booked)

        # ----------------------------------------------------
        # 2. Check My Appointments
        # ----------------------------------------------------
        my_res = self.client.get("/api/appointments/my/")
        self.assertEqual(my_res.status_code, status.HTTP_200_OK)
        results = my_res.data if isinstance(my_res.data, list) else my_res.data.get("results", [])
        self.assertTrue(any(a["id"] == appointment_id for a in results))

        # ----------------------------------------------------
        # 3. Reschedule appointment to Slot 2
        # ----------------------------------------------------
        reschedule_res = self.client.post(
            f"/api/appointments/{appointment_id}/reschedule/",
            {"new_slot_id": self.slot2.id},
            format="json",
        )
        self.assertEqual(reschedule_res.status_code, status.HTTP_200_OK)

        self.slot1.refresh_from_db()
        self.slot2.refresh_from_db()
        self.assertFalse(self.slot1.is_booked, "Slot 1 should be freed after reschedule")
        self.assertTrue(self.slot2.is_booked, "Slot 2 should now be booked")

        # ----------------------------------------------------
        # 4. Cancel the appointment
        # ----------------------------------------------------
        cancel_res = self.client.post(
            f"/api/appointments/{appointment_id}/cancel/",
            {"reason": "Changed plans entirely"},
            format="json",
        )
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)

        self.slot2.refresh_from_db()
        self.assertFalse(self.slot2.is_booked, "Slot 2 should be freed after cancellation")

        appt = Appointment.objects.get(id=appointment_id)
        self.assertEqual(appt.status, "CANCELLED")
        self.assertEqual(appt.cancellation_reason, "Changed plans entirely")
        self.assertEqual(appt.cancelled_by, "PATIENT")
