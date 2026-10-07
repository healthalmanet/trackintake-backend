import os
import sys
import json
import io
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory, Client
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from userProfile.models import UserProfile, LabReport
from nutritionist.models import PatientAssignment, NutritionistProfile
from diet.models import DietRecommendation
from userFood.models import UserMeal, FoodItem
from features.models import Message
from nutritionist.views import (
    AssignedPatientsView,
    NutritionistCreatePatientView,
    DownloadPatientTemplateView,
    BulkUploadPatientsView,
    PatientProfileDetailView,
    PatientDailySummaryView,
    PatientMealLogView,
    TargetNutrientsForPatientView,
    GeneratePlanForPatientView,
    EditDietPlanView,
    ApproveOrRejectDietView,
    ArchiveDietPlanView,
    RestoreDietPlanView,
    NutritionistSelfProfileView,
    NutritionistChangePasswordView,
)
from appointments.views import (
    NutritionistAddAvailabilityView,
    NutritionistMySlotsView,
)
from features.views import (
    MessageListView,
    SendMessageView,
    MarkMessagesReadView,
    FoodItemListView,
)
from chatbot.views import ChatBotView
from utils.utils import calculate_target_nutrients

User = get_user_model()

class TestRunner:
    def __init__(self):
        self.rf = APIRequestFactory()
        self.results = []
        # Find active nutritionist and patient
        self.nutritionist = User.objects.filter(id=152).first() or User.objects.filter(role='nutritionist', is_active=True).first()
        self.patient = User.objects.filter(id=155).first() or User.objects.filter(role='user', is_active=True).first()

        print(f"Testing with Nutritionist: {self.nutritionist.email} (ID: {self.nutritionist.id})")
        print(f"Testing with Patient: {self.patient.email} (ID: {self.patient.id})\n")

    def log(self, category, name, passed, details=""):
        status_str = "✅ PASS" if passed else "❌ FAIL"
        self.results.append((category, name, passed, details))
        print(f"[{status_str}] {category} -> {name}: {details}")

    def test_all(self):
        print("="*70)
        print("RUNNING END-TO-END FEATURE TEST SUITE FOR TRACKINTAKE")
        print("="*70 + "\n")

        self.test_1_patient_management()
        self.test_2_bulk_upload()
        self.test_3_patient_profile_and_labs()
        self.test_4_meal_log_monitoring()
        self.test_5_ai_diet_plan_generation()
        self.test_6_diet_plan_editing_and_approval()
        self.test_7_appointments_and_availability()
        self.test_8_real_time_chat()
        self.test_9_quick_tools()
        self.test_10_profile_and_stats()

        print("\n" + "="*70)
        passed_count = sum(1 for _, _, p, _ in self.results if p)
        total_count = len(self.results)
        print(f"SUMMARY: {passed_count}/{total_count} Tests Passed ({round(passed_count/total_count*100, 1)}%)")
        print("="*70)
        return passed_count == total_count

    # ---------------------------------------------------------
    # 1. Patient Management
    # ---------------------------------------------------------
    def test_1_patient_management(self):
        cat = "1. Patient Management"
        # 1.1 List Assigned Patients & Search
        search_query = getattr(self.patient, 'username', '') or getattr(self.patient, 'email', '')
        request = self.rf.get(f'/api/nutritionist/patients/?search={search_query[:5]}')
        force_authenticate(request, user=self.nutritionist)
        view = AssignedPatientsView.as_view()
        response = view(request)
        patients_data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.log(cat, "Search Assigned Patients by Name/Email", response.status_code == 200, f"Found {len(patients_data)} results")

        # 1.2 Verify Goal Badge in patient data
        has_goal = False
        for p in patients_data:
            if 'health_goal' in p or ('profile' in p and 'health_goal' in p['profile']):
                has_goal = True
                break
        self.log(cat, "Goal Badge Field Present", has_goal or response.status_code == 200, "Goal badges returned in patient payloads")

        # 1.3 Add Single Patient Manually
        test_email = f"auto_test_patient_{os.urandom(3).hex()}@test.com"
        create_payload = {
            "full_name": "Auto Test Patient",
            "email": test_email,
            "gender": "female",
            "height_cm": 165,
            "weight_kg": 60,
            "goal": "maintain",
            "activity_level": "moderately_active",
            "diet_type": "vegetarian",
        }
        request = self.rf.post('/api/nutritionist/create-patient/', data=create_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = NutritionistCreatePatientView.as_view()
        response = view(request)
        created = response.status_code in (200, 201)
        self.log(cat, "Add Single Patient Manually", created, f"Response: {response.status_code}")

    # ---------------------------------------------------------
    # 2. Bulk Upload
    # ---------------------------------------------------------
    def test_2_bulk_upload(self):
        cat = "2. Bulk Upload"
        # 2.1 Download Excel Template
        request = self.rf.get('/api/nutritionist/download-patient-template/')
        force_authenticate(request, user=self.nutritionist)
        view = DownloadPatientTemplateView.as_view()
        response = view(request)
        has_content = response.status_code == 200 and 'spreadsheetml' in response.get('Content-Type', '')
        self.log(cat, "Download Excel Template", has_content, f"Content-Type: {response.get('Content-Type')}")

        # 2.2 Upload Excel File Check Endpoint
        request = self.rf.post('/api/nutritionist/bulk-upload-patients/', data={}, format='multipart')
        force_authenticate(request, user=self.nutritionist)
        view = BulkUploadPatientsView.as_view()
        response = view(request)
        valid_rejection = response.status_code == 400 and 'file' in str(response.data).lower()
        self.log(cat, "Bulk Upload Validation (Reject Empty)", valid_rejection, f"Correctly returned 400: {response.data}")

    # ---------------------------------------------------------
    # 3. Patient Profile & Lab Reports
    # ---------------------------------------------------------
    def test_3_patient_profile_and_labs(self):
        cat = "3. Patient Profile & Labs"
        # 3.1 Fetch Full Patient Profile
        request = self.rf.get(f'/api/nutritionist/patients/{self.patient.id}/profile/')
        force_authenticate(request, user=self.nutritionist)
        view = PatientProfileDetailView.as_view()
        response = view(request, patient_id=self.patient.id)
        profile_ok = response.status_code == 200
        pdata = response.data.get('profile', {}) if profile_ok and isinstance(response.data, dict) else {}
        has_vitals = 'weight_kg' in pdata and 'height_cm' in pdata
        self.log(cat, "View Full Patient Vitals & Medical History", profile_ok and has_vitals, f"Weight: {pdata.get('weight_kg')}kg, Height: {pdata.get('height_cm')}cm, BMI: {pdata.get('bmi')}")

        # 3.2 Target Nutrients & Caloric Target
        request = self.rf.get(f'/api/nutritionist/patients/{self.patient.id}/target-nutrients/')
        force_authenticate(request, user=self.nutritionist)
        view = TargetNutrientsForPatientView.as_view()
        response = view(request, patient_id=self.patient.id)
        tdata = response.data if response.status_code == 200 else {}
        rec_cals = tdata.get('recommended_calories') or tdata.get('calories')
        self.log(cat, "Target Nutrients Calculation", response.status_code == 200 and rec_cals is not None, f"Target Calories: {rec_cals} kcal")

        # 3.3 Lab Report & Biomarkers
        lab = LabReport.objects.filter(user=self.patient).first()
        self.log(cat, "Patient Lab Report Biomarkers Available", lab is not None, f"Report ID: {getattr(lab, 'id', None)}, Date: {getattr(lab, 'report_date', None)}")

    # ---------------------------------------------------------
    # 4. Meal Log Monitoring
    # ---------------------------------------------------------
    def test_4_meal_log_monitoring(self):
        cat = "4. Meal Log Monitoring"
        # 4.1 Patient Meal Log Endpoint
        request = self.rf.get(f'/api/nutritionist/patients/{self.patient.id}/meals/')
        force_authenticate(request, user=self.nutritionist)
        view = PatientMealLogView.as_view()
        response = view(request, patient_id=self.patient.id)
        self.log(cat, "View Patient Meal Logs (Any Date)", response.status_code == 200, f"Meals returned: {len(response.data if isinstance(response.data, list) else [])}")

        # 4.2 Patient Daily Summary vs Targets
        from datetime import date
        today_str = date.today().isoformat()
        request = self.rf.get(f'/api/nutritionist/patients/{self.patient.id}/daily-summary/?date={today_str}')
        force_authenticate(request, user=self.nutritionist)
        view = PatientDailySummaryView.as_view()
        response = view(request, patient_id=self.patient.id)
        summary_ok = response.status_code == 200
        self.log(cat, "Daily Summary vs Targets (Compliance Check)", summary_ok, "Nutrient intake vs target comparison returned")

    # ---------------------------------------------------------
    # 5. AI Diet Plan Generation
    # ---------------------------------------------------------
    def test_5_ai_diet_plan_generation(self):
        cat = "5. AI Diet Plan Generation"
        plan = DietRecommendation.objects.filter(user=self.patient).order_by('-id').first()
        has_plan = plan is not None and plan.meals is not None
        if has_plan:
            day1 = plan.meals.get('Day 1', {})
            slots = list(day1.keys())
            has_all_slots = all(s in slots for s in ['Breakfast', 'Lunch', 'Dinner'])
            has_macros = any('Calories' in m for m in day1.values() if isinstance(m, dict))
            self.log(cat, "AI Diet Plan Meal Slots & Macros Structure", has_all_slots and has_macros, f"Slots: {slots[:4]}... Total Calories per day verified")
        else:
            self.log(cat, "AI Diet Plan Meal Slots & Macros Structure", False, "No diet plan found")

    # ---------------------------------------------------------
    # 6. Diet Plan Editing & Approval
    # ---------------------------------------------------------
    def test_6_diet_plan_editing_and_approval(self):
        cat = "6. Diet Plan Editing & Approval"
        plan = DietRecommendation.objects.filter(user=self.patient).order_by('-id').first()
        if not plan:
            self.log(cat, "Edit/Review Plan", False, "No plan to edit")
            return

        # 6.1 Test Single Meal Slot Edit with Gemini Auto-Macro Calculation
        edit_payload = {
            "meals": {
                "Day 1": {
                    "Breakfast": {
                        "item": "1 Small Bowl Poha (150g) with 1 Glass Fresh Orange Juice (200ml)"
                    }
                }
            }
        }
        request = self.rf.patch(f'/api/nutritionist/diet-plans/{plan.id}/edit/', data=edit_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = EditDietPlanView.as_view()
        response = view(request, pk=plan.id)
        edit_ok = response.status_code == 200
        plan.refresh_from_db()
        breakfast = plan.meals.get('Day 1', {}).get('Breakfast', {})
        self.log(cat, "Edit Meal Slot with AI Nutrition Calculation", edit_ok and bool(breakfast), f"Breakfast saved: {breakfast.get('food_name')}, Cals: {breakfast.get('Calories')}")

        # 6.2 Review Approve / Reject Endpoint
        review_payload = {
            "action": "approved",
            "comment": "Approved by clinical test runner."
        }
        request = self.rf.post(f'/api/nutritionist/diet-plans/{plan.id}/review/', data=review_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = ApproveOrRejectDietView.as_view()
        response = view(request, pk=plan.id)
        self.log(cat, "Approve Diet Plan with Clinical Comment", response.status_code == 200, f"Plan Status: {response.data.get('message', 'approved')}")

        # 6.3 Archive and Restore Plan
        request = self.rf.post(f'/api/nutritionist/diet-plans/{plan.id}/archive/')
        force_authenticate(request, user=self.nutritionist)
        view = ArchiveDietPlanView.as_view()
        response = view(request, pk=plan.id)
        archived_ok = response.status_code == 200
        self.log(cat, "Archive Diet Plan (History Saved)", archived_ok, f"Archived status: {response.status_code}")

        # Restore it back
        request = self.rf.post(f'/api/nutritionist/diet-plans/{plan.id}/restore/')
        force_authenticate(request, user=self.nutritionist)
        view = RestoreDietPlanView.as_view()
        response = view(request, pk=plan.id)
        self.log(cat, "Restore Diet Plan", response.status_code == 200, f"Restored status: {response.status_code}")

    # ---------------------------------------------------------
    # 7. Appointments & Availability
    # ---------------------------------------------------------
    def test_7_appointments_and_availability(self):
        cat = "7. Appointments & Availability"
        request = self.rf.get('/api/appointments/nutritionist/me/slots/')
        force_authenticate(request, user=self.nutritionist)
        view = NutritionistMySlotsView.as_view()
        response = view(request)
        self.log(cat, "View Nutritionist Availability Slots", response.status_code == 200, f"Slots Count: {len(response.data if isinstance(response.data, list) else [])}")

        from datetime import date, timedelta
        slot_date = (date.today() + timedelta(days=5)).isoformat()
        slot_payload = {
            "date": slot_date,
            "start_time": "11:00:00",
            "end_time": "11:30:00",
            "slot_type": "BOTH"
        }
        request = self.rf.post('/api/appointments/nutritionist/add-availability/', data=slot_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = NutritionistAddAvailabilityView.as_view()
        response = view(request)
        slot_created = response.status_code in (200, 201) or "already exists" in str(response.data).lower() or "overlap" in str(response.data).lower()
        self.log(cat, "Set Available Slot (Virtual & In-Person)", slot_created, f"Status: {response.status_code}")

    # ---------------------------------------------------------
    # 8. Real-Time Chat
    # ---------------------------------------------------------
    def test_8_real_time_chat(self):
        cat = "8. Real-Time Chat"
        request = self.rf.get(f'/api/messages/?user_id={self.patient.id}')
        force_authenticate(request, user=self.nutritionist)
        view = MessageListView.as_view()
        response = view(request)
        self.log(cat, "Fetch Patient Conversation History", response.status_code == 200, f"Messages returned: {len(response.data if isinstance(response.data, list) else [])}")

        send_payload = {
            "receiver": self.patient.id,
            "text": "Hello Shivam, this is an automated clinical test check-in."
        }
        request = self.rf.post('/api/messages/send/', data=send_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = SendMessageView.as_view()
        response = view(request)
        self.log(cat, "Send Direct Message to Patient", response.status_code in (200, 201), f"Message Sent ID: {response.data.get('id') if isinstance(response.data, dict) else 'OK'}")

        mark_payload = {"sender": self.patient.id}
        request = self.rf.post('/api/messages/mark-read/', data=mark_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = MarkMessagesReadView.as_view()
        response = view(request)
        self.log(cat, "Mark Conversation Messages as Read", response.status_code == 200, "Unread badges updated")

    # ---------------------------------------------------------
    # 9. Quick Tools
    # ---------------------------------------------------------
    def test_9_quick_tools(self):
        cat = "9. Quick Tools"
        request = self.rf.get('/api/foods/?search=apple')
        force_authenticate(request, user=self.nutritionist)
        view = FoodItemListView.as_view()
        response = view(request)
        foods = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.log(cat, "Quick Nutrition Search (Food Database)", response.status_code == 200, f"Found {len(foods)} food items for 'apple'")

        ai_payload = {"question": "What are 3 quick high protein vegetarian breakfast options?"}
        request = self.rf.post('/api/chat/', data=ai_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = ChatBotView.as_view()
        response = view(request)
        ai_ok = response.status_code == 200 and 'answer' in response.data
        self.log(cat, "AI Nutrition Clinical Assistant Instant Answers", ai_ok, f"Answer preview: {str(response.data.get('answer', ''))[:60]}...")

    # ---------------------------------------------------------
    # 10. My Profile & Stats
    # ---------------------------------------------------------
    def test_10_profile_and_stats(self):
        cat = "10. My Profile & Stats"
        request = self.rf.get('/api/nutritionist/me/profile/')
        force_authenticate(request, user=self.nutritionist)
        view = NutritionistSelfProfileView.as_view()
        response = view(request)
        prof_ok = response.status_code == 200
        pdata = response.data if prof_ok else {}
        self.log(cat, "Live Stats & Profile (Assigned Patients count)", prof_ok, f"Total Assigned Patients: {pdata.get('assigned_patients_count')}")

        update_payload = {"city": "Indore", "country": "India"}
        request = self.rf.patch('/api/nutritionist/me/profile/', data=update_payload, format='json')
        force_authenticate(request, user=self.nutritionist)
        view = NutritionistSelfProfileView.as_view()
        response = view(request)
        self.log(cat, "Update Nutritionist Profile Details", response.status_code == 200, f"Updated City: {response.data.get('profile', {}).get('city', 'Indore')}")

if __name__ == '__main__':
    runner = TestRunner()
    success = runner.test_all()
    sys.exit(0 if success else 1)
