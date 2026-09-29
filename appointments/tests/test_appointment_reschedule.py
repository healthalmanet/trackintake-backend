from datetime import date, time, timedelta, datetime
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from appointments.models import Appointment, AvailabilitySlot, AppointmentReminder
from nutritionist.models import NutritionistProfile

User = get_user_model()


class AppointmentRescheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.patient = User.objects.create_user(
            email="patient_reschedule@example.com",
            full_name="Patient Reschedule",
            password="testpassword123",
            role="user",
        )
        self.other_patient = User.objects.create_user(
            email="other_patient@example.com",
            full_name="Other Patient",
            password="testpassword123",
            role="user",
        )
        self.nutritionist = User.objects.create_user(
            email="nutri_reschedule@example.com",
            full_name="Dr. Nutri Reschedule",
            password="testpassword123",
            role="nutritionist",
        )
        self.other_nutritionist = User.objects.create_user(
            email="other_nutri@example.com",
            full_name="Dr. Other Nutri",
            password="testpassword123",
            role="nutritionist",
        )
        self.nutri_profile = self.nutritionist.nutritionist_profile
        self.nutri_profile.nutritionist_type = NutritionistProfile.NutritionistType.INHOUSE
        self.nutri_profile.online_price = 500.00
        self.nutri_profile.save()

        # Dates far enough in future (> 24 hours)
        self.future_date_1 = timezone.localdate() + timedelta(days=5)
        self.future_date_2 = timezone.localdate() + timedelta(days=6)
        self.future_date_3 = timezone.localdate() + timedelta(days=7)

        # Slots
        self.initial_slot = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.future_date_1,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type="VIRTUAL",
            is_booked=True,
        )

        self.new_slot_1 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.future_date_2,
            start_time=time(11, 0),
            end_time=time(11, 30),
            slot_type="VIRTUAL",
            is_booked=False,
        )

        self.new_slot_2 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.future_date_3,
            start_time=time(15, 0),
            end_time=time(15, 30),
            slot_type="VIRTUAL",
            is_booked=False,
        )

        # Initial Appointment
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            nutritionist=self.nutritionist,
            slot=self.initial_slot,
            slot_date=self.initial_slot.date,
            slot_start_time=self.initial_slot.start_time,
            slot_end_time=self.initial_slot.end_time,
            appointment_category="IN_HOUSE",
            appointment_type="VIRTUAL",
            assigned_by="SYSTEM",
            status="CONFIRMED",
            fee_amount=500.00,
            payment_status="PAID",
            meeting_link="https://zoom.us/j/old-link",
        )

    @patch("appointments.views.send_reschedule_emails")
    @patch("appointments.views.create_zoom_meeting")
    def test_reschedule_success_by_patient(self, mock_zoom, mock_email):
        """Patient can successfully reschedule at least 24h prior to appointment."""
        mock_zoom.return_value = {"join_url": "https://zoom.us/j/new-rescheduled-zoom"}
        self.client.force_authenticate(user=self.patient)

        url = f"/api/appointments/{self.appointment.id}/reschedule/"
        response = self.client.post(url, {"new_slot_id": self.new_slot_1.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("reschedules_used"), 1)
        self.assertEqual(response.data.get("reschedules_remaining"), 1)

        # Verify old slot freed
        self.initial_slot.refresh_from_db()
        self.assertFalse(self.initial_slot.is_booked)

        # Verify new slot claimed
        self.new_slot_1.refresh_from_db()
        self.assertTrue(self.new_slot_1.is_booked)

        # Verify appointment updated
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.slot_id, self.new_slot_1.id)
        self.assertEqual(self.appointment.slot_date, self.new_slot_1.date)
        self.assertEqual(self.appointment.slot_start_time, self.new_slot_1.start_time)
        self.assertEqual(self.appointment.reschedule_count, 1)
        self.assertIsNotNone(self.appointment.rescheduled_at)
        self.assertEqual(self.appointment.meeting_link, "https://zoom.us/j/new-rescheduled-zoom")

        # Verify email dispatched
        mock_email.assert_called_once()

    def test_reschedule_within_24_hours_blocked_for_patient(self):
        """Patient cannot reschedule if appointment starts within 24 hours."""
        # Set appointment timing to 3 hours in the future in active timezone
        near_future = timezone.localtime() + timedelta(hours=3)
        self.appointment.slot_date = near_future.date()
        self.appointment.slot_start_time = near_future.time().replace(microsecond=0)
        self.appointment.save()

        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/reschedule/"
        response = self.client.post(url, {"new_slot_id": self.new_slot_1.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at least 24 hours", response.data.get("detail", ""))

    @patch("appointments.views.send_reschedule_emails")
    @patch("appointments.views.create_zoom_meeting")
    def test_reschedule_limit_max_2_attempts(self, mock_zoom, mock_email):
        """Patient is strictly capped at 2 reschedules per appointment."""
        mock_zoom.return_value = {"join_url": "https://zoom.us/j/mock"}
        self.client.force_authenticate(user=self.patient)

        # 1st Reschedule
        res1 = self.client.post(f"/api/appointments/{self.appointment.id}/reschedule/", {"new_slot_id": self.new_slot_1.id})
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # 2nd Reschedule
        res2 = self.client.post(f"/api/appointments/{self.appointment.id}/reschedule/", {"new_slot_id": self.new_slot_2.id})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.reschedule_count, 2)

        # Create a 3rd slot for 3rd attempt
        slot_3 = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=timezone.localdate() + timedelta(days=10),
            start_time=time(16, 0),
            end_time=time(16, 30),
            slot_type="VIRTUAL",
            is_booked=False,
        )

        # 3rd Reschedule attempt -> MUST BE REJECTED
        res3 = self.client.post(f"/api/appointments/{self.appointment.id}/reschedule/", {"new_slot_id": slot_3.id})
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum limit of 2 reschedules", res3.data.get("detail", ""))

    def test_unauthorized_user_cannot_reschedule(self):
        """A different user who is not patient or nutritionist cannot reschedule."""
        self.client.force_authenticate(user=self.other_patient)
        url = f"/api/appointments/{self.appointment.id}/reschedule/"
        response = self.client.post(url, {"new_slot_id": self.new_slot_1.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_reschedule_cancelled_appointment(self):
        """Rescheduling an already cancelled appointment must fail."""
        self.appointment.status = "CANCELLED"
        self.appointment.save()

        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/reschedule/"
        response = self.client.post(url, {"new_slot_id": self.new_slot_1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot reschedule a cancelled appointment", response.data.get("detail", ""))

    def test_cannot_reschedule_to_different_nutritionist_slot(self):
        """Slot must belong to the same nutritionist assigned to the appointment."""
        other_slot = AvailabilitySlot.objects.create(
            nutritionist=self.other_nutritionist,
            date=self.future_date_2,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type="VIRTUAL",
            is_booked=False,
        )
        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/reschedule/"
        response = self.client.post(url, {"new_slot_id": other_slot.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assigned nutritionist", response.data.get("detail", ""))

    def test_cannot_reschedule_to_already_booked_slot(self):
        """Cannot reschedule to a slot that has already been booked."""
        self.new_slot_1.is_booked = True
        self.new_slot_1.save()

        self.client.force_authenticate(user=self.patient)
        url = f"/api/appointments/{self.appointment.id}/reschedule/"
        response = self.client.post(url, {"new_slot_id": self.new_slot_1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already booked", response.data.get("detail", ""))
