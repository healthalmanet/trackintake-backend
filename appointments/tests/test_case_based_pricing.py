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


class CaseBasedPricingAndExpertTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Patient
        self.patient = User.objects.create_user(
            email="patient_case@example.com",
            full_name="Patient Case",
            password="testpassword123",
            role="user",
        )

        # In-House Nutritionist
        self.inhouse_nutri = User.objects.create_user(
            email="inhouse_case@example.com",
            full_name="Dr. Inhouse Case",
            password="testpassword123",
            role="nutritionist",
        )
        self.inhouse_profile = self.inhouse_nutri.nutritionist_profile
        self.inhouse_profile.nutritionist_type = NutritionistProfile.NutritionistType.INHOUSE
        self.inhouse_profile.online_price = 499.00
        self.inhouse_profile.offline_price = 599.00
        self.inhouse_profile.offline_payment_required = False
        self.inhouse_profile.save()

        # Specialist Expert Nutritionist
        self.expert_nutri = User.objects.create_user(
            email="expert_case@example.com",
            full_name="Dr. Expert Specialist",
            password="testpassword123",
            role="nutritionist",
        )
        self.expert_profile = self.expert_nutri.nutritionist_profile
        self.expert_profile.nutritionist_type = NutritionistProfile.NutritionistType.EXPERT
        self.expert_profile.online_price = 1200.00
        self.expert_profile.offline_price = 1500.00
        self.expert_profile.offline_payment_required = False
        self.expert_profile.save()

        self.slot_date = timezone.localdate() + timedelta(days=2)

    def test_inhouse_nutri_cannot_create_variable_slot(self):
        """In-house nutritionist slots must always be FIXED, even if VARIABLE is requested."""
        self.client.force_authenticate(user=self.inhouse_nutri)
        res = self.client.post("/api/appointments/nutritionist/add-availability/", {
            "date": str(self.slot_date),
            "start_time": "09:00",
            "end_time": "09:30",
            "slot_type": "VIRTUAL",
            "pricing_mode": "VARIABLE"
        }, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        slot = AvailabilitySlot.objects.get(nutritionist=self.inhouse_nutri, start_time=time(9, 0))
        # Enforced as FIXED
        self.assertEqual(slot.pricing_mode, "FIXED")

    def test_expert_can_create_variable_slot(self):
        """Expert nutritionist can create variable pricing slots."""
        self.client.force_authenticate(user=self.expert_nutri)
        res = self.client.post("/api/appointments/nutritionist/add-availability/", {
            "date": str(self.slot_date),
            "start_time": "10:00",
            "end_time": "10:30",
            "slot_type": "VIRTUAL",
            "pricing_mode": "VARIABLE"
        }, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        slot = AvailabilitySlot.objects.get(nutritionist=self.expert_nutri, start_time=time(10, 0))
        self.assertEqual(slot.pricing_mode, "VARIABLE")

    def test_variable_slot_booking_lifecycle(self):
        """
        End-to-End Test:
        1. Expert creates variable slot.
        2. Patient books variable slot with case summary -> PENDING_REVIEW.
        3. Expert reviews case and quotes fee -> AWAITING_PAYMENT.
        4. Patient confirms payment -> CONFIRMED.
        """
        # 1. Expert slot
        slot = AvailabilitySlot.objects.create(
            nutritionist=self.expert_nutri,
            date=self.slot_date,
            start_time=time(11, 0),
            end_time=time(11, 30),
            slot_type="VIRTUAL",
            pricing_mode="VARIABLE",
            is_booked=False,
        )

        # 2. Patient books variable slot
        self.client.force_authenticate(user=self.patient)
        book_res = self.client.post("/api/appointments/book/", {
            "slot_id": slot.id,
            "appointment_category": "EXPERT",
            "expert_id": self.expert_nutri.id,
            "appointment_type": "VIRTUAL",
            "patient_case_summary": "Experiencing recurring insulin resistance and chronic fatigue for 6 months.",
            "patient_medical_conditions": ["Diabetes Type 2", "Thyroid"],
        }, format="json")

        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED)
        appt_id = book_res.data["id"]
        appt = Appointment.objects.get(id=appt_id)
        self.assertEqual(appt.status, "PENDING_REVIEW")
        self.assertEqual(appt.pricing_mode, "VARIABLE")
        self.assertEqual(appt.payment_status, "UNPAID")
        self.assertEqual(appt.fee_amount, 0)
        self.assertEqual(appt.patient_case_summary, "Experiencing recurring insulin resistance and chronic fatigue for 6 months.")

        slot.refresh_from_db()
        self.assertTrue(slot.is_booked)

        # 3. Non-expert or patient cannot set price
        self.client.force_authenticate(user=self.patient)
        bad_price_res = self.client.post(f"/api/appointments/{appt_id}/set-price/", {
            "fee_amount": 1800,
            "note": "Hacking price",
        }, format="json")
        self.assertEqual(bad_price_res.status_code, status.HTTP_403_FORBIDDEN)

        # Expert quotes price
        self.client.force_authenticate(user=self.expert_nutri)
        quote_res = self.client.post(f"/api/appointments/{appt_id}/set-price/", {
            "price": 1800,
            "note": "Includes 60-min endocrine workup & custom meal plan.",
        }, format="json")
        self.assertEqual(quote_res.status_code, status.HTTP_200_OK)

        appt.refresh_from_db()
        self.assertEqual(appt.status, "AWAITING_PAYMENT")
        self.assertEqual(appt.fee_amount, 1800.0)
        self.assertEqual(appt.nutritionist_quote_note, "Includes 60-min endocrine workup & custom meal plan.")
        self.assertIsNotNone(appt.price_quoted_at)

        # 4. Patient confirms payment
        self.client.force_authenticate(user=self.patient)
        with patch("appointments.zoom_service.create_zoom_meeting", return_value={"join_url": "https://zoom.us/test-zoom"}):
            confirm_res = self.client.post(f"/api/appointments/{appt_id}/confirm-payment/", {}, format="json")
        
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "CONFIRMED")
        self.assertEqual(appt.payment_status, "PAID")
        self.assertEqual(appt.payout_status, "PENDING")
        self.assertEqual(appt.payout_amount, 1800.0)

    def test_expert_declines_case_frees_slot(self):
        """When an expert declines a case review, slot is freed and status is DECLINED."""
        slot = AvailabilitySlot.objects.create(
            nutritionist=self.expert_nutri,
            date=self.slot_date,
            start_time=time(14, 0),
            end_time=time(14, 30),
            slot_type="VIRTUAL",
            pricing_mode="VARIABLE",
            is_booked=False,
        )

        self.client.force_authenticate(user=self.patient)
        book_res = self.client.post("/api/appointments/book/", {
            "slot_id": slot.id,
            "appointment_category": "EXPERT",
            "expert_id": self.expert_nutri.id,
            "appointment_type": "VIRTUAL",
            "patient_case_summary": "Need pediatric nutrition consult.",
        }, format="json")
        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED)
        appt_id = book_res.data["id"]

        # Expert declines
        self.client.force_authenticate(user=self.expert_nutri)
        decline_res = self.client.post(f"/api/appointments/{appt_id}/decline-case/", {
            "reason": "I specialize in adult metabolic health only."
        }, format="json")
        self.assertEqual(decline_res.status_code, status.HTTP_200_OK)

        appt = Appointment.objects.get(id=appt_id)
        self.assertEqual(appt.status, "DECLINED")
        self.assertEqual(appt.cancellation_reason, "I specialize in adult metabolic health only.")

        slot.refresh_from_db()
        self.assertFalse(slot.is_booked)

    def test_in_person_pay_at_clinic_confirmation(self):
        """Patient can choose pay at clinic for quoted in-person consultation if offline_payment_required is False."""
        slot = AvailabilitySlot.objects.create(
            nutritionist=self.expert_nutri,
            date=self.slot_date,
            start_time=time(16, 0),
            end_time=time(16, 30),
            slot_type="IN_PERSON",
            pricing_mode="VARIABLE",
            is_booked=False,
        )

        self.client.force_authenticate(user=self.patient)
        book_res = self.client.post("/api/appointments/book/", {
            "slot_id": slot.id,
            "appointment_category": "EXPERT",
            "expert_id": self.expert_nutri.id,
            "appointment_type": "IN_PERSON",
            "patient_case_summary": "In-clinic sports nutrition consultation.",
        }, format="json")
        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED)
        appt_id = book_res.data["id"]

        # Expert quotes fee
        self.client.force_authenticate(user=self.expert_nutri)
        set_price_res = self.client.post(f"/api/appointments/{appt_id}/set-price/", {
            "price": 1500,
            "note": "Standard in-clinic physical assessment.",
        }, format="json")
        self.assertEqual(set_price_res.status_code, status.HTTP_200_OK)

        # Patient confirms with pay-at-clinic
        self.client.force_authenticate(user=self.patient)
        confirm_res = self.client.post(f"/api/appointments/{appt_id}/confirm-payment/", {
            "pay_at_clinic": True
        }, format="json")
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)

        appt = Appointment.objects.get(id=appt_id)
        self.assertEqual(appt.status, "CONFIRMED")
        self.assertEqual(appt.payment_status, "UNPAID")
