from datetime import date, time, timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from appointments.models import Appointment, AvailabilitySlot
from nutritionist.models import NutritionistProfile, PatientAssignment

User = get_user_model()


class AppointmentBookingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Patient
        self.patient = User.objects.create_user(
            email="patient_booking@example.com",
            full_name="Patient Booking",
            password="testpassword123",
            role="user",
        )

        # Create Nutritionist
        self.nutritionist = User.objects.create_user(
            email="nutri_booking@example.com",
            full_name="Dr. Nutri Booking",
            password="testpassword123",
            role="nutritionist",
        )
        self.nutri_profile = self.nutritionist.nutritionist_profile
        self.nutri_profile.nutritionist_type = NutritionistProfile.NutritionistType.INHOUSE
        self.nutri_profile.online_price = 0.00
        self.nutri_profile.offline_price = 0.00
        self.nutri_profile.offline_payment_required = False
        self.nutri_profile.save()

        # Create Expert Nutritionist
        self.expert = User.objects.create_user(
            email="expert_booking@example.com",
            full_name="Dr. Expert Booking",
            password="testpassword123",
            role="nutritionist",
        )
        self.expert_profile = self.expert.nutritionist_profile
        self.expert_profile.nutritionist_type = NutritionistProfile.NutritionistType.EXPERT
        self.expert_profile.online_price = 0.00
        self.expert_profile.offline_price = 0.00
        self.expert_profile.save()

        # Tomorrow's date
        self.slot_date = timezone.localdate() + timedelta(days=2)

        # Availability Slots
        self.virtual_slot = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.slot_date,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type="VIRTUAL",
            is_booked=False,
        )

        self.in_person_slot = AvailabilitySlot.objects.create(
            nutritionist=self.nutritionist,
            date=self.slot_date,
            start_time=time(11, 0),
            end_time=time(11, 30),
            slot_type="IN_PERSON",
            is_booked=False,
        )

        self.expert_slot = AvailabilitySlot.objects.create(
            nutritionist=self.expert,
            date=self.slot_date,
            start_time=time(14, 0),
            end_time=time(14, 30),
            slot_type="BOTH",
            is_booked=False,
        )

    def test_unauthenticated_cannot_book(self):
        """Unauthenticated requests must be rejected with 401."""
        response = self.client.post("/api/appointments/book/", {
            "slot_id": self.virtual_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("appointments.serializers.send_booking_confirmation_emails")
    @patch("appointments.serializers.create_zoom_meeting")
    def test_book_inhouse_virtual_success(self, mock_zoom, mock_email):
        """Patient can successfully book an in-house virtual slot."""
        mock_zoom.return_value = {"join_url": "https://zoom.us/j/test-meeting-123"}
        self.client.force_authenticate(user=self.patient)

        payload = {
            "slot_id": self.virtual_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check slot is marked booked
        self.virtual_slot.refresh_from_db()
        self.assertTrue(self.virtual_slot.is_booked)

        # Check appointment created
        appt = Appointment.objects.filter(patient=self.patient, slot=self.virtual_slot).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.status, "CONFIRMED")
        self.assertEqual(appt.appointment_category, "IN_HOUSE")
        self.assertEqual(appt.appointment_type, "VIRTUAL")
        self.assertEqual(appt.meeting_link, "https://zoom.us/j/test-meeting-123")
        self.assertEqual(appt.nutritionist, self.nutritionist)

        # Check auto patient assignment
        assignment = PatientAssignment.objects.filter(patient=self.patient, nutritionist=self.nutritionist).first()
        self.assertIsNotNone(assignment)

    @patch("appointments.serializers.send_booking_confirmation_emails")
    @patch("appointments.serializers.create_zoom_meeting")
    def test_book_expert_appointment_success(self, mock_zoom, mock_email):
        """Patient can successfully book an expert slot by selecting expert_id."""
        mock_zoom.return_value = {"join_url": "https://zoom.us/j/test-expert-meeting"}
        self.client.force_authenticate(user=self.patient)

        payload = {
            "slot_id": self.expert_slot.id,
            "appointment_category": "EXPERT",
            "appointment_type": "VIRTUAL",
            "expert_id": self.expert.id,
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.expert_slot.refresh_from_db()
        self.assertTrue(self.expert_slot.is_booked)

        appt = Appointment.objects.get(slot=self.expert_slot)
        self.assertEqual(appt.appointment_category, "EXPERT")
        self.assertEqual(appt.selected_expert, self.expert)
        self.assertEqual(appt.nutritionist, self.expert)

    def test_book_already_booked_slot_fails(self):
        """Attempting to book a slot that is already booked returns 400 error."""
        self.virtual_slot.is_booked = True
        self.virtual_slot.save()

        self.client.force_authenticate(user=self.patient)
        payload = {
            "slot_id": self.virtual_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_book_nonexistent_slot_fails(self):
        """Attempting to book with invalid slot ID returns 400 error."""
        self.client.force_authenticate(user=self.patient)
        payload = {
            "slot_id": 999999,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_book_mismatched_slot_type_fails(self):
        """Booking an IN_PERSON slot as VIRTUAL should be rejected by validation."""
        self.client.force_authenticate(user=self.patient)
        payload = {
            "slot_id": self.in_person_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "VIRTUAL",
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("appointments.serializers.send_booking_confirmation_emails")
    def test_in_person_pay_at_clinic_when_offline_payment_not_required(self, mock_email):
        """When nutritionist allows Pay at Clinic (offline_payment_required=False), booking is UNPAID."""
        self.nutri_profile.offline_price = 500.00
        self.nutri_profile.offline_payment_required = False
        self.nutri_profile.pending_offline_payment_required = None
        self.nutri_profile.save()

        self.client.force_authenticate(user=self.patient)
        payload = {
            "slot_id": self.in_person_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "IN_PERSON",
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        appt = Appointment.objects.get(slot=self.in_person_slot)
        self.assertEqual(appt.payment_status, "UNPAID")
        self.assertEqual(appt.payout_status, "NOT_APPLICABLE")
        self.assertEqual(float(appt.fee_amount), 500.00)

    def test_in_person_payment_required_blocks_free_booking(self):
        """When offline_payment_required=True, booking without payment is rejected with consultation_required."""
        self.nutri_profile.offline_price = 600.00
        self.nutri_profile.offline_payment_required = True
        self.nutri_profile.pending_offline_payment_required = None
        self.nutri_profile.save()

        self.client.force_authenticate(user=self.patient)
        payload = {
            "slot_id": self.in_person_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "IN_PERSON",
        }
        response = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data.get("consultation_required"))
        self.assertEqual(float(response.data.get("price")), 600.00)
        self.assertTrue(response.data.get("offline_payment_required"))

    @patch("appointments.serializers.send_booking_confirmation_emails")
    def test_nutritionist_can_mark_appointment_paid_at_clinic(self, mock_email):
        """Nutritionist can mark an UNPAID in-clinic appointment as PAID once cash is collected."""
        self.nutri_profile.offline_price = 350.00
        self.nutri_profile.offline_payment_required = False
        self.nutri_profile.save()

        self.client.force_authenticate(user=self.patient)
        payload = {
            "slot_id": self.in_person_slot.id,
            "appointment_category": "IN_HOUSE",
            "appointment_type": "IN_PERSON",
        }
        res = self.client.post("/api/appointments/book/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        appt_id = res.data["id"]

        # Patient cannot mark as paid
        self.client.force_authenticate(user=self.patient)
        res_fail = self.client.post(f"/api/appointments/{appt_id}/mark-paid/")
        self.assertEqual(res_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Attending nutritionist marks as paid
        self.client.force_authenticate(user=self.nutritionist)
        res_ok = self.client.post(f"/api/appointments/{appt_id}/mark-paid/")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data["payment_status"], "PAID")

        appt = Appointment.objects.get(id=appt_id)
        self.assertEqual(appt.payment_status, "PAID")
        self.assertEqual(appt.payout_status, "NOT_APPLICABLE")
