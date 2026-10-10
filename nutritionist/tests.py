from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from nutritionist.models import PatientAssignment
from subscriptions.models import Plan, UserSubscription
from userProfile.models import LabReport, UserProfile

User = get_user_model()


class NutritionistLabReportTests(TestCase):
    """
    Integration tests for Nutritionist managing patient lab reports:
    - Listing reports (empty & populated)
    - Creating/uploading lab report with biomarker fields & file
    - Updating existing report
    - Deleting report
    - Authorization & patient assignment checks
    """

    def setUp(self):
        self.client = APIClient()

        # Create practitioner plan
        self.plan = Plan.objects.create(
            name="Practitioner Pro",
            plan_type="nutritionist",
            price=1999.00,
            duration_days=30,
            nutri_lab_reports_allowed=True,
            nutri_max_patients=50,
        )

        # 1. Nutritionist user
        self.nutritionist = User.objects.create_user(
            email="nutritionist@example.com",
            full_name="Dr. Sarah Nutrition",
            password="Password123!",
            role="nutritionist",
        )
        UserSubscription.objects.create(
            user=self.nutritionist,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            is_active=True,
        )

        # 2. Patient user
        self.patient = User.objects.create_user(
            email="patient@example.com",
            full_name="John Patient",
            password="Password123!",
            role="user",
        )
        self.patient_profile, _ = UserProfile.objects.get_or_create(user=self.patient)

        # 3. Patient Assignment (nutritionist <-> patient)
        PatientAssignment.objects.get_or_create(
            nutritionist=self.nutritionist,
            patient=self.patient,
        )

        # 4. Other (unassigned) nutritionist
        self.other_nutritionist = User.objects.create_user(
            email="other_nutri@example.com",
            full_name="Dr. Other",
            password="Password123!",
            role="nutritionist",
        )
        UserSubscription.objects.create(
            user=self.other_nutritionist,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            is_active=True,
        )

    def test_get_patient_lab_reports_empty(self):
        """Nutritionist can list lab reports for patient; returns empty list if none exist."""
        self.client.force_authenticate(user=self.nutritionist)
        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 0)

    def test_create_lab_report_with_biomarkers(self):
        """Nutritionist can create a lab report with biomarker measurements."""
        self.client.force_authenticate(user=self.nutritionist)
        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/"

        payload = {
            "report_date": "2026-10-10",
            "weight_kg": "75.5",
            "height_cm": "178",
            "blood_pressure_systolic": "120",
            "blood_pressure_diastolic": "80",
            "fasting_blood_sugar": "95.5",
            "hba1c": "5.4",
            "ldl_cholesterol": "110",
            "hdl_cholesterol": "50",
            "triglycerides": "140",
            "vitamin_d3": "35",
        }

        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify created in DB
        created_report = LabReport.objects.filter(user=self.patient).first()
        self.assertIsNotNone(created_report)
        self.assertEqual(str(created_report.report_date), "2026-10-10")
        self.assertEqual(created_report.weight_kg, 75.5)
        self.assertEqual(created_report.blood_pressure_systolic, 120)
        self.assertEqual(created_report.blood_pressure_diastolic, 80)
        self.assertEqual(created_report.fasting_blood_sugar, 95.5)
        self.assertEqual(created_report.hba1c, 5.4)

    def test_create_lab_report_with_file_upload(self):
        """Nutritionist can upload a PDF/Image document with the lab report."""
        self.client.force_authenticate(user=self.nutritionist)
        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/"

        mock_file = SimpleUploadedFile(
            "sample_lab_report.pdf",
            b"%PDF-1.4 mock content for testing lab report",
            content_type="application/pdf"
        )

        payload = {
            "report_date": "2026-10-09",
            "fasting_blood_sugar": "100",
            "report_file": mock_file,
        }

        response = self.client.post(url, data=payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        report = LabReport.objects.filter(user=self.patient, report_date="2026-10-09").first()
        self.assertIsNotNone(report)
        self.assertTrue(bool(report.report_file))

    def test_update_lab_report(self):
        """Nutritionist can update an existing lab report."""
        self.client.force_authenticate(user=self.nutritionist)
        report = LabReport.objects.create(
            user=self.patient,
            report_date=date(2026, 10, 1),
            fasting_blood_sugar=120,
            blood_pressure_systolic=135,
        )

        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/{report.id}/"
        update_payload = {
            "fasting_blood_sugar": "99.0",
            "blood_pressure_systolic": "118",
        }

        response = self.client.patch(url, data=update_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        report.refresh_from_db()
        self.assertEqual(report.fasting_blood_sugar, 99.0)
        self.assertEqual(report.blood_pressure_systolic, 118)

    def test_delete_lab_report(self):
        """Nutritionist can delete a lab report for their assigned patient."""
        self.client.force_authenticate(user=self.nutritionist)
        report = LabReport.objects.create(
            user=self.patient,
            report_date=date(2026, 10, 5),
            fasting_blood_sugar=110,
        )

        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/{report.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LabReport.objects.filter(id=report.id).exists())

    def test_unassigned_nutritionist_cannot_access_or_add_report(self):
        """Nutritionist not assigned to patient is forbidden from accessing or creating reports."""
        self.client.force_authenticate(user=self.other_nutritionist)
        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/"

        # GET forbidden
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, status.HTTP_403_FORBIDDEN)

        # POST forbidden
        post_res = self.client.post(url, data={"report_date": "2026-10-10", "fasting_blood_sugar": "100"})
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_access_nutritionist_lab_reports_endpoint(self):
        """Non-practitioner users are forbidden from accessing nutritionist-scoped lab report endpoint."""
        self.client.force_authenticate(user=self.patient)
        url = f"/api/nutritionist/patients/{self.patient.id}/lab-reports/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
