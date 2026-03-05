# # your_app/services.py

# # ==============================================================================
# # Diet Plan Generation Service (Definitive Version for Data-Rich Legacy Schema)
# # ==============================================================================
# # This service file is engineered to produce the EXACT legacy JSON format
# # of your original system. It includes a runnable test block at the bottom.
# # ==============================================================================

# import json
# import traceback
# from datetime import date, datetime
# import google.generativeai as genai
# from time import sleep

# import os, logging
# logger = logging.getLogger(__name__)

# # --- Standalone Script Imports & Setup ---
# # This block allows the script to run outside of Django for testing purposes.
# try:
#     from django.conf import settings
#     from django.db import transaction
#     from django.contrib.auth import get_user_model
#     from django.utils import timezone
#     from userProfile.models import UserProfile, LabReport, DietRecommendation
#     # Load the key from Django settings if running within the app

#     API_KEY = getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY')

# except ImportError:
#     # If Django is not available, set up minimal mocks and a hardcoded key for testing
#     print("⚠️ Django environment not detected. Running in standalone test mode.")
#     settings, transaction, get_user_model, timezone = None, None, None, None
#     UserProfile, LabReport, DietRecommendation = type('Mock', (object,), {}), type('Mock', (object,), {}), type('Mock', (object,), {})
#     API_KEY = "your-google-ai-api-key-here" # ⬅️ PASTE YOUR API KEY HERE FOR STANDALONE TESTING

# # Configure the API Key
# if API_KEY:

#     genai.configure(api_key=API_KEY)
#     logger.info("Gemini API configured from environment.")
# else:
#     logger.error("GEMINI_API_KEY is not configured. AI calls will fail.")


# # --- Internal Helper Functions (Already finalized and correct) ---
# def _serialize_user_profile(profile) -> dict:
#     """Serializes a complete UserProfile model (or a mock object) into a dictionary."""
#     return {"date_of_birth": profile.date_of_birth.strftime('%Y-%m-%d') if profile.date_of_birth else None,"country": profile.country,"gender": profile.gender,"occupation": profile.occupation,"height_cm": profile.height_cm,"weight_kg": profile.weight_kg,"activity_level": profile.activity_level,"goal": profile.goal,"diet_type": profile.diet_type,"allergies": profile.allergies,"is_diabetic": profile.is_diabetic,"is_hypertensive": profile.is_hypertensive,"has_heart_condition": profile.has_heart_condition,"has_thyroid_disorder": profile.has_thyroid_disorder,"has_arthritis": profile.has_arthritis,"has_gastric_issues": profile.has_gastric_issues,"other_chronic_condition": profile.other_chronic_condition,"family_history": profile.family_history,"is_pregnant": profile.is_pregnant,"due_date": profile.due_date.strftime('%Y-%m-%d') if profile.due_date else None,"is_breastfeeding": profile.is_breastfeeding,"current_trimester": getattr(profile, 'current_trimester', None),}
# def _serialize_lab_report(report) -> dict:
#     """Serializes a complete LabReport model (or a mock object) into a dictionary."""
#     if not report: return {}
#     return {"waist_circumference_cm": report.waist_circumference_cm, "blood_pressure_systolic": report.blood_pressure_systolic, "blood_pressure_diastolic": report.blood_pressure_diastolic, "fasting_blood_sugar": report.fasting_blood_sugar, "postprandial_sugar": report.postprandial_sugar, "hba1c": report.hba1c, "ldl_cholesterol": report.ldl_cholesterol, "hdl_cholesterol": report.hdl_cholesterol, "triglycerides": report.triglycerides, "crp": report.crp, "esr": report.esr, "uric_acid": report.uric_acid, "creatinine": report.creatinine, "urea": report.urea, "alt": report.alt, "ast": report.ast, "vitamin_d3": report.vitamin_d3, "vitamin_b12": report.vitamin_b12, "tsh": report.tsh, }
# def _calculate_target_nutrients(data: dict) -> dict:
#     """Calculates nutritional targets with robust safety checks."""
#     try:
#         today = date.today(); dob = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
#         age = today.year-dob.year-((today.month,today.day)<(dob.month,today.day))
#         w,h,g,goal,act = data['weight_kg'],data['height_cm'],data['gender'].lower(),data['goal'].lower(),data['activity_level'].lower()
#     except (KeyError,TypeError,AttributeError) as e: raise ValueError(f"Profile incomplete for calculation: {e}")
#     bmr=10*w+6.25*h-5*age+(5 if g=="male" else -161)
#     mults={"sedentary":1.2,"lightly active":1.375,"moderately active":1.55,"very active":1.725,"extra active":1.9}
#     key=next((k for k in mults if act.startswith(k)),"sedentary")
#     rec_cals=bmr*mults[key]
#     is_female=g!='male'
#     if data.get('is_pregnant') and is_female:
#         goal='maintain weight'; rec_cals += 340 if data.get('current_trimester')==2 else (450 if data.get('current_trimester')==3 else 0)
#     elif data.get('is_breastfeeding') and is_female:rec_cals+=500
#     if"gain"in goal:rec_cals+=400
#     elif"lose"in goal:rec_cals-=500
#     protein_g=round(w*1.8)
#     if(data.get('is_pregnant') or data.get('is_breastfeeding')) and is_female:protein_g=max(protein_g,round(w*1.1)+25)
#     fats_g=round(w*0.8)
#     carbs_g=round((rec_cals-(protein_g*4+fats_g*9))/4) if rec_cals>(protein_g*4+fats_g*9) else 0
#     return{"recommended_calories":round(rec_cals),"protein_g":protein_g,"carbs_g":carbs_g,"fats_g":fats_g}

# def _call_gemini_for_single_day_structured(profile: dict, targets: dict, day_number: int, used_foods: set) -> dict:
#     """Generates a structured, data-rich meal plan for ONE day."""
#     prompt = f"""You are an expert clinical dietitian generating Day {day_number} of a 15-day meal plan. User's health profile: {json.dumps(profile)}. Approximate daily targets to guide portion sizes: {json.dumps(targets)}. --- 🔴 CRITICAL INSTRUCTIONS 🔴 --- 1. **Quantity and Nutrients are Mandatory:** For each meal, the `food_name` must include the exact quantity and unit (e.g., "2 rotis (50 g each)", "200 ml milk"), along with the full nutritional breakdown (`Calories`, `Protein`, `Fats`, `Carbs`, `Sugar`, `Fiber`, `Gram_Equivalent`). 2. **Nutritional Accuracy:** The nutritional values MUST correspond to the specified food and quantity. 3. **Variety:** AVOID using main dishes from this list: {', '.join(sorted(list(used_foods)))}. 4. **JSON Only:** Output ONLY a single, valid JSON object. Keys MUST be meal names, and nutritional keys MUST be PascalCase. --- JSON SCHEMA FOR THIS SINGLE DAY --- {{"Early-Morning": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, ... }},"Breakfast": {{ "food_name": "<str>", "quantity": "<str>", ... }}, "Mid-Morning Snack": {{ ... }},"Lunch": {{ ... }}, "Afternoon Snack": {{ ... }},"Dinner": {{ ... }},"Bedtime": {{ ... }} }} """
#     try:
#         if not API_KEY: raise ValueError("GEMINI_API_KEY is not configured.")
#         model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
#         config = genai.types.GenerationConfig(temperature=0.4, response_mime_type="application/json")
#         response = model.generate_content(prompt, generation_config=config)
#         return json.loads(response.text)
#     except Exception as e:
#         traceback.print_exc()
#         return {"error": f"AI call failed for Day {day_number}: {e}"}

# def _call_gemini_for_flags(profile: dict, report: dict) -> list:
#     """A small, separate, reliable call to get just the suggestion flags."""
#     prompt = f"Analyze this health profile: {json.dumps(profile)} and lab report: {json.dumps(report)}. Return a JSON list of suggestion flags like [\"promote_healthy_fats\", \"anti_inflammatory\"]. Your output MUST be ONLY the JSON list."
#     try:
#         if not API_KEY: return []
#         model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
#         config = genai.types.GenerationConfig(temperature=0.0, response_mime_type="application/json")
#         response = model.generate_content(prompt, generation_config=config)
#         return json.loads(response.text)
#     except: return []

# # --- Main Public Service Function ---
# # This decorator is only active when running within Django
# db_transaction = transaction.atomic if transaction else lambda func: func

# @db_transaction
# def generate_ai_plan_for_patient(patient_id: int, nutritionist_id: int):
#     User = get_user_model()
#     try:
#         patient, nutritionist = User.objects.get(id=patient_id, role='user'), User.objects.get(id=nutritionist_id)
#         profile, report = UserProfile.objects.get(user=patient), LabReport.objects.filter(user=patient).order_by('-report_date').first()
#         profile_dict, report_dict = _serialize_user_profile(profile), _serialize_lab_report(report)
#         targets_dict = _calculate_target_nutrients(profile_dict)
#         legacy_plan_json = {}
#         used_foods = set()
#         for day_num in range(1, 4):
#             daily_plan = _call_gemini_for_single_day_structured(profile_dict, targets_dict, day_num, used_foods)
#             if "error" in daily_plan: return None, f"AI generation failed on Day {day_num}: {daily_plan['error']}"
#             legacy_plan_json[f"Day {day_num}"] = daily_plan
#             for meal in daily_plan.values(): used_foods.add(meal.get("food_name"))
#             sleep(1)
#         flags = _call_gemini_for_flags(profile_dict, report_dict)
#         legacy_plan_json["suggestion_flags"] = flags
#         full_snapshot = {"profile": profile_dict, "lab_report": report_dict, "targets": targets_dict}
#         new_plan = DietRecommendation.objects.create(user=patient, for_week_starting=timezone.now().date(), meals=legacy_plan_json, original_ai_plan=legacy_plan_json, user_profile_snapshot=full_snapshot, status='pending', reviewed_by=nutritionist, nutritionist_comment="Plan generated by nutritionist.")
#         return new_plan, None
#     except (User.DoesNotExist, UserProfile.DoesNotExist, ValueError) as e:
#         return None, str(e)
#     except Exception as e:
#         traceback.print_exc()
#         return None, f"An unexpected server error occurred: {e}"


# # ==============================================================================
# # SECTION 3: STANDALONE TEST HARNESS (CORRECTED)
# # This block is only executed when you run `python your_app/services.py`.
# # ==============================================================================
# if __name__ == '__main__':
#     print("\n" + "="*80)
#     print("🚀 RUNNING SERVICE FILE IN STANDALONE TEST MODE 🚀")
#     print("="*80)

#     # This helper class mimics a Django model instance.
#     class MockModel:
#         def __init__(self, **kwargs):
#             self.__dict__.update(kwargs)
#             for field in ["is_pregnant", "due_date", "is_breastfeeding"]:
#                 if not hasattr(self, field): setattr(self, field, None)
            
#         @property
#         def current_trimester(self):
#              if not self.is_pregnant or not self.due_date: return None
#              weeks = 40 - ((self.due_date - date.today()).days / 7)
#              if weeks < 14: return 1
#              elif 14 <= weeks < 28: return 2
#              else: return 3

#     # --- Step 1: Create Complete Sample Data ---
#     mock_user_profile = MockModel(
#         date_of_birth=date(1988, 5, 20), country="India", gender="Male",
#         occupation="Software Developer", height_cm=178.0, weight_kg=95.0,
#         activity_level="Sedentary (little or no exercise)", goal="Lose Weight",
#         diet_type="Vegetarian", allergies="None", is_diabetic=True, is_hypertensive=True,
#         has_heart_condition=False, has_thyroid_disorder=False, has_arthritis=True,
#         has_gastric_issues=True, other_chronic_condition="Occasional acid reflux.",
#         family_history="Father has Type 2 Diabetes.",
#     )

#     # UPDATED: This object now includes all required fields with sample or None values.
#     mock_lab_report = MockModel(
#         waist_circumference_cm=105.0, blood_pressure_systolic=140,
#         blood_pressure_diastolic=90, fasting_blood_sugar=135.0,
#         postprandial_sugar=190.0, hba1c=7.1, ldl_cholesterol=160.0,
#         hdl_cholesterol=38.0, triglycerides=210.0, crp=6.0, esr=28.0,
#         uric_acid=7.8, creatinine=1.0, urea=40.0, alt=50.0, ast=42.0,
#         vitamin_d3=15.0, vitamin_b12=450.0, tsh=3.5
#     )

#     print("\n--- 1. SIMULATED INPUT DATA ---")
#     profile_data = _serialize_user_profile(mock_user_profile)
#     lab_data = _serialize_lab_report(mock_lab_report)
#     print("UserProfile Data:\n", json.dumps(profile_data, indent=2))
#     print("\nLabReport Data:\n", json.dumps(lab_data, indent=2))
    
#     try:
#         targets = _calculate_target_nutrients(profile_data)
#         print("\n--- 2. CALCULATED NUTRITIONAL TARGETS ---")
#         print(json.dumps(targets, indent=2))
#     except ValueError as e:
#         print(f"\n❌ ERROR: Could not calculate targets. {e}")
#         exit()

#     print("\n--- 3. TESTING AI CALL FOR A SINGLE DAY ---")
#     test_day_plan = _call_gemini_for_single_day_structured(
#         profile=profile_data, targets=targets, day_number=3,
#         used_foods={'Dal Makhani', 'Jeera Rice'}
#     )
    
#     print("\n--- 4. AI-GENERATED JSON FOR A SINGLE DAY ---")
#     if "error" in test_day_plan:
#         print(f"❌ AI CALL FAILED: {test_day_plan['error']}")
#     else:
#         print(json.dumps(test_day_plan, indent=2))

#     print("\n" + "="*80)
#     print("✅ STANDALONE TEST COMPLETE ✅")
#     print("="*80)