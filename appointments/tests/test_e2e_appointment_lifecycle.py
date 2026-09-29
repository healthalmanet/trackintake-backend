"""
End-to-End System Integration Test for Appointments:
Simulates frontend-to-backend API flows for:
1. Appointment Discovery & Booking
2. Appointment Rescheduling (Policy & Limit Enforcement)
3. Appointment Cancellation (Policy & Slot Release)
4. State Consistency across Patient & Nutritionist Views
"""
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


class EndToEndAppointmentLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Setup Patient
        self.patient = User.objects.create_user(
            email="e2e_patient@example.com",
            full_name="E2E Patient",
            password="securepassword123",
            role="user",
        )

        # 2. Setup Nutritionist
        self.nutritionist = User.objects.create_user(
            email="e2e_nutritionist@example.com",
            full_name="Dr. E2E Practitioner",
            password="securepassword123",
            role="nutritionist",
        )
        self.profile = self.nutritionist.nutritionist_profile
        self.profile.online_price = 0.00
        self.profile.offline_price = 0.00
        self.profile.offline_payment_required = False
        self.profile.save()

        # 3. Setup Dates
        self.day_initial = timezone.localdate() + timedelta(days=4)
        self.day_resched_1 = timezone.localdate() + timedelta(days=6)
        self.day_resched_2 = timezone.localdate() + timedelta(days=8)
        self.day_resched_3 = timezone.localdate() + timedelta(days=10)

        # 4. Setup Slots
        self.slot_initial = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.day_initial,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type="BOTH",
            is_booked=False,
        )

        self.slot_resched_1 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.day_resched_1,
            start_time=time(11, 0),
            end_time=time(11, 30),
            slot_type="BOTH",
            is_booked=False,
        )

        self.slot_resched_2 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.day_resched_2,
            start_time=time(15, 0),
            end_time=time(15, 30),
            slot_type="BOTH",
            is_booked=False,
        )

        self.slot_resched_3 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.day_resched_3,
            start_time=time(16, 0),
            end_time=time(16, 30),
            slot_type="BOTH",
            is_booked=False,
        )

    @patch("appointments.serializers.send_booking_confirmation_emails")
    @patch("appointments.serializers.create_zoom_meeting")
    @patch("appointments.views.create_zoom_meeting")
    @patch("appointments.views.send_reschedule_emails")
    @patch("appointments.views.send_cancellation_emails")
    def test_complete_frontend_backend_lifecycle(
        self,
        mock_cancel_email,
        mock_resched_email,
        mock_resched_zoom,
        mock_book_zoom,
        mock_booking_email,
    ):
        mock_book_zoom.return_value = {"join_url": "https://zoom.us/j/e2e-initial"}
        mock_resched_zoom.return_value = {"join_url": "https://zoom.us/j/e2e-rescheduled"}

        # Authenticate as patient
        self.client.force_authenticate(user=self.patient)

        # STEP 1: Query Available Slots for Nutritionist on initial date
        slots_resp = self.client.get(
            f"/api/appointments/nutritionist/{self.nutritionist.id}/slots/",
            {"date": self.day_initial.isoformat(), "appointment_type": "VIRTUAL"},
        )
        self.assertEqual(slots_resp.status_code, status.HTTP_200_OK)
        available_slots = slots_resp.data if isinstance(slots_resp.data, list) else slots_resp.data.get("results", [])
        self.assertTrue(any(s["id"] == self.slot_initial.id for s in available_slots))

        # STEP 2: Book Appointment (Frontend bookAppointment call)
        book_payload = {
            "slot_id": self.slot_initial.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        }
        book_resp = self.client.post("/api/appointments/book/", book_payload, format="json")
        self.assertEqual(book_resp.status_code, status.HTTP_201_CREATED)
        appointment_id = book_resp.data["id"]

        # Verify initial slot is now marked booked
        self.slot_initial.refresh_from_db()
        self.assertTrue(self.slot_initial.is_booked)

        # STEP 3: Verify Appointment in My Appointments List
        my_resp = self.client.get("/api/appointments/my/")
        self.assertEqual(my_resp.status_code, status.HTTP_200_OK)
        my_list = my_resp.data if isinstance(my_resp.data, list) else my_resp.data.get("results", [])
        booked_appt = next((a for a in my_list if a["id"] == appointment_id), None)
        self.assertIsNotNone(booked_appt)
        self.assertEqual(booked_appt["status"], "CONFIRMED")
        self.assertEqual(booked_appt["reschedule_count"], 0)

        # STEP 4: First Reschedule to slot_resched_1 (Frontend rescheduleAppointment call)
        resched_payload_1 = {"new_slot_id": self.slot_resched_1.id}
        resched_resp_1 = self.client.post(
            f"/api/appointments/appointments/{appointment_id}/reschedule/",
            resched_payload_1,
            format="json",
        )
        self.assertEqual(resched_resp_1.status_code, status.HTTP_200_OK)
        self.assertEqual(resched_resp_1.data["reschedules_used"], 1)
        self.assertEqual(resched_resp_1.data["reschedules_remaining"], 1)

        # Verify old slot is freed and new slot is booked
        self.slot_initial.refresh_from_db()
        self.slot_resched_1.refresh_from_db()
        self.assertFalse(self.slot_initial.is_booked, "Initial slot must be freed")
        self.assertTrue(self.slot_resched_1.is_booked, "Rescheduled slot 1 must be booked")

        # STEP 5: Second Reschedule to slot_resched_2
        resched_payload_2 = {"new_slot_id": self.slot_resched_2.id}
        resched_resp_2 = self.client.post(
            f"/api/appointments/appointments/{appointment_id}/reschedule/",
            resched_payload_2,
            format="json",
        )
        self.assertEqual(resched_resp_2.status_code, status.HTTP_200_OK)
        self.assertEqual(resched_resp_2.data["reschedules_used"], 2)
        self.assertEqual(resched_resp_2.data["reschedules_remaining"], 0)

        self.slot_resched_1.refresh_from_db()
        self.slot_resched_2.refresh_from_db()
        self.assertFalse(self.slot_resched_1.is_booked, "Slot 1 must now be freed")
        self.assertTrue(self.slot_resched_2.is_booked, "Slot 2 must now be booked")

        # STEP 6: Third Reschedule Attempt -> Policy strictly prohibits >2 attempts
        resched_payload_3 = {"new_slot_id": self.slot_resched_3.id}
        resched_resp_3 = self.client.post(
            f"/api/appointments/appointments/{appointment_id}/reschedule/",
            resched_payload_3,
            format="json",
        )
        self.assertEqual(resched_resp_3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum limit of 2 reschedules", resched_resp_3.data["detail"])
        self.slot_resched_3.refresh_from_db()
        self.assertFalse(self.slot_resched_3.is_booked, "Slot 3 must remain unbooked")

        # STEP 7: Cancel Appointment (Frontend cancelAppointment call)
        cancel_payload = {"reason": "Schedule resolved, session no longer required"}
        cancel_resp = self.client.post(
            f"/api/appointments/appointments/{appointment_id}/cancel/",
            cancel_payload,
            format="json",
        )
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertIn("cancelled successfully", cancel_resp.data["detail"])

        # Verify active slot is immediately freed
        self.slot_resched_2.refresh_from_db()
        self.assertFalse(self.slot_resched_2.is_booked, "Active slot must be freed upon cancellation")

        # Verify database appointment status
        appt = Appointment.objects.get(id=appointment_id)
        self.assertEqual(appt.status, "CANCELLED")
        self.assertEqual(appt.cancelled_by, "PATIENT")
        self.assertEqual(appt.cancellation_reason, "Schedule resolved, session no longer required")

        # STEP 8: Attempting to reschedule or cancel a cancelled appointment must fail
        resched_cancelled = self.client.post(
            f"/api/appointments/appointments/{appointment_id}/reschedule/",
            {"new_slot_id": self.slot_resched_3.id},
            format="json",
        )
        self.assertEqual(resched_cancelled.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot reschedule a cancelled appointment", resched_cancelled.data["detail"])

        cancel_again = self.client.post(
            f"/api/appointments/appointments/{appointment_id}/cancel/",
            {"reason": "Cancel again"},
            format="json",
        )
        self.assertEqual(cancel_again.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been cancelled", cancel_again.data["detail"])
