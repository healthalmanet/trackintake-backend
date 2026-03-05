# your_app/services.py

# ==============================================================================
# Diet Plan Generation Service (Definitive Version for Data-Rich Legacy Schema)
# ==============================================================================
# This service file is engineered to produce the EXACT legacy JSON format
# of your original system, including all nutritional values. It uses a robust
# iterative loop to ensure reliability and prevent JSON decoding errors.
# ==============================================================================

import json
import traceback
from datetime import date, datetime
import google.generativeai as genai
from time import sleep

from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from userProfile.models import UserProfile, LabReport
from diet.models import DietRecommendation
import os
import dotenv
from google.api_core.exceptions import ResourceExhausted
from django.db import close_old_connections
dotenv.load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)


# --- Internal Helper Functions (No changes needed here) ---
def _serialize_user_profile(profile: UserProfile) -> dict:
    """Serializes the complete UserProfile model into a dictionary."""
    return {"date_of_birth": profile.date_of_birth.strftime('%Y-%m-%d') if profile.date_of_birth else None,"country": profile.country,"city": profile.city,"gender": profile.gender,"occupation": profile.occupation,"height_cm": profile.height_cm,"weight_kg": profile.weight_kg,"activity_level": profile.activity_level,"goal": profile.goal,"diet_type": profile.diet_type,"allergies": profile.allergies,"is_diabetic": profile.is_diabetic,"is_hypertensive": profile.is_hypertensive,"has_heart_condition": profile.has_heart_condition,"has_thyroid_disorder": profile.has_thyroid_disorder,"has_arthritis": profile.has_arthritis,"has_gastric_issues": profile.has_gastric_issues,"other_chronic_condition": profile.other_chronic_condition,"family_history": profile.family_history,"is_pregnant": profile.is_pregnant,"due_date": profile.due_date.strftime('%Y-%m-%d') if profile.due_date else None,"is_breastfeeding": profile.is_breastfeeding,"current_trimester": profile.current_trimester,}
def _serialize_lab_report(report: LabReport | None) -> dict:
    """Serializes the complete LabReport model into a dictionary."""
    if not report: return {}
    return {"waist_circumference_cm": report.waist_circumference_cm, "blood_pressure_systolic": report.blood_pressure_systolic, "blood_pressure_diastolic": report.blood_pressure_diastolic, "fasting_blood_sugar": report.fasting_blood_sugar, "postprandial_sugar": report.postprandial_sugar, "hba1c": report.hba1c, "ldl_cholesterol": report.ldl_cholesterol, "hdl_cholesterol": report.hdl_cholesterol, "triglycerides": report.triglycerides, "crp": report.crp, "esr": report.esr, "uric_acid": report.uric_acid, "creatinine": report.creatinine, "urea": report.urea, "alt": report.alt, "ast": report.ast, "vitamin_d3": report.vitamin_d3, "vitamin_b12": report.vitamin_b12, "tsh": report.tsh, }
def _calculate_target_nutrients(data: dict) -> dict:
    """Calculates nutritional targets with robust safety checks."""
    try:
        today = date.today(); dob = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        age = today.year-dob.year-((today.month,today.day)<(dob.month,today.day))
        w,h,g,goal,act = data['weight_kg'],data['height_cm'],data['gender'].lower(),data['goal'].lower(),data['activity_level'].lower()
    except (KeyError,TypeError,AttributeError) as e: raise ValueError(f"Profile incomplete for calculation: {e}")
    bmr=10*w+6.25*h-5*age+(5 if g=="male" else -161)
    mults={"sedentary":1.2,"lightly active":1.375,"moderately active":1.55,"very active":1.725,"extra active":1.9}
    key=next((k for k in mults if act.startswith(k)),"sedentary")
    rec_cals=bmr*mults[key]
    is_female=g!='male'
    if data.get('is_pregnant') and is_female:
        goal='maintain weight'; rec_cals += 340 if data.get('current_trimester')==2 else (450 if data.get('current_trimester')==3 else 0)
    elif data.get('is_breastfeeding') and is_female:rec_cals+=500
    if"gain"in goal:rec_cals+=400
    elif"lose"in goal:rec_cals-=500
    protein_g=round(w*1.8)
    if(data.get('is_pregnant') or data.get('is_breastfeeding')) and is_female:protein_g=max(protein_g,round(w*1.1)+25)
    fats_g=round(w*0.8)
    carbs_g=round((rec_cals-(protein_g*4+fats_g*9))/4) if rec_cals>(protein_g*4+fats_g*9) else 0
    return{"recommended_calories":round(rec_cals),"protein_g":protein_g,"carbs_g":carbs_g,"fats_g":fats_g}


def _call_gemini_for_single_day_structured(profile: dict, targets: dict, day_number: int, used_foods: set) -> dict:
    """
    Generates a structured, data-rich meal plan for ONE day. This is the robust method.
    The prompt commands the AI to include the `quantity` field and all nutritional values.
    """
    # ============================ START: THE ONLY CHANGE IS HERE ============================
    prompt = f"""
You are an expert clinical dietitian generating Day {day_number} of a 3-day meal plan.

User's health profile:
{json.dumps(profile)}

Approximate daily targets to guide portion sizes:
{json.dumps(targets)}

--- 🌍 LOCATION-SPECIFIC INSTRUCTIONS ---
1. The meal plan MUST strictly follow the food culture of:
   - Country: {profile.get("country")}
   - City (if available): {profile.get("city", "Not specified")}

2. Use ingredients, cooking styles, and traditional dishes commonly eaten in that specific country and city.
   - Prefer locally available grains, vegetables, fruits, oils, and proteins.
   - Avoid foreign or imported dishes unless they are commonly consumed in that region.
   - Consider regional cooking oils (e.g., mustard oil in North India, coconut oil in South India, olive oil in Mediterranean countries).
   - Consider regional staple carbs (e.g., rice vs roti vs millet vs bread depending on geography).
   - Adjust spice level based on cultural norms of that region.

3. If the country is India:
   - Adjust dishes based on city/region (North Indian, South Indian, East Indian, West Indian patterns).
   - Use traditional Indian meal structure.

4. If city is coastal → include more seafood options (if diet_type allows).
5. If region is known for vegetarian culture → prefer vegetarian options unless user diet_type says otherwise.
6. Consider seasonal and locally accessible produce in that region.
    --- 🔴 CRITICAL INSTRUCTIONS 🔴 ---
    1.  **`Sugar` and `Fiber` are NON-NEGOTIABLE:** You MUST include `Sugar` and `Fiber` keys with numeric values for every single food item. Do not omit them under any circumstances.
    2.  **Full Nutritional Breakdown:** For each meal, the `food_name` must include an exact quantity and unit (e.g., "2 rotis (50 g each)"). You MUST also provide the full nutritional breakdown: `Calories`, `Protein`, `Fats`, `Carbs`, `Sugar`, `Fiber`, and `Gram_Equivalent`.
    3.  **Nutritional Accuracy:** The nutritional values MUST be accurate for the specified food and quantity.
    4.  **Variety:** AVOID using main dishes from this list: {', '.join(sorted(list(used_foods)))}.
    5.  **JSON Only:** Output ONLY a single, valid JSON object with PascalCase keys for nutrients.

    --- JSON SCHEMA FOR THIS SINGLE DAY ---
    {{
      "Early-Morning": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
      "Breakfast": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
      "Mid-Morning Snack": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
      "Lunch": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
      "Afternoon Snack": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
      "Dinner": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
      "Bedtime": {{ "food_name": "<str>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }}
    }}
    """
    # ============================= END: THE ONLY CHANGE IS HERE =============================
    try:
        if not API_KEY: raise ValueError("GEMINI_API_KEY is not configured.")
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        config = genai.types.GenerationConfig(temperature=0.4, response_mime_type="application/json")
        response = model.generate_content(prompt, generation_config=config)
        return json.loads(response.text)
    except ResourceExhausted:
        # 🔴 VERY IMPORTANT
        return {
            "error": "AI_QUOTA_EXCEEDED"
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"AI call failed for Day {day_number}: {e}"}

def _call_gemini_for_flags(profile: dict, report: dict) -> list:
    """A small, separate, reliable call to get just the suggestion flags."""
    prompt = f"Analyze this health profile: {json.dumps(profile)} and lab report: {json.dumps(report)}. Return a JSON list of suggestion flags like [\"promote_healthy_fats\", \"anti_inflammatory\"]. Your output MUST be ONLY the JSON list."
    try:
        if not API_KEY: return []
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        config = genai.types.GenerationConfig(temperature=0.0, response_mime_type="application/json")
        response = model.generate_content(prompt, generation_config=config)
        return json.loads(response.text)
    except: return [] # Fail silently if flags can't be generated






def generate_ai_plan_for_patient(profile_dict, report_dict, targets_dict):
    """
    PURE AI FUNCTION.
    No Django ORM.
    No DB access.
    No connection handling.
    """

    try:
        full_plan_json = {}
        used_foods = set()

        for day_num in range(1, 4):

            print(f"Generating structured plan for Day {day_num}...")

            daily_plan = _call_gemini_for_single_day_structured(
                profile_dict,
                targets_dict,
                day_num,
                used_foods
            )

            if daily_plan.get("error") == "AI_QUOTA_EXCEEDED":
                return None, "AI quota exceeded. Try later."

            if "error" in daily_plan:
                return None, daily_plan["error"]

            full_plan_json[f"Day {day_num}"] = daily_plan

            for meal in daily_plan.values():
                if isinstance(meal, dict):
                    used_foods.add(meal.get("food_name"))

            sleep(1)

        flags = _call_gemini_for_flags(profile_dict, report_dict)
        full_plan_json["suggestion_flags"] = flags

        return full_plan_json, None

    except Exception as e:
        traceback.print_exc()
        return None, str(e)

# ==============================================================================
# SECTION 2: MAIN PUBLIC SERVICE FUNCTION (No changes needed here)
# ==============================================================================
# @transaction.atomic
# def generate_ai_plan_for_patient(patient_id: int, nutritionist_id: int):
#     User = get_user_model()
#     try:
#         patient, nutritionist = User.objects.get(id=patient_id, role='user'), User.objects.get(id=nutritionist_id)
#         profile, report = UserProfile.objects.get(user=patient), LabReport.objects.filter(user=patient).order_by('-report_date').first()
#         profile_dict, report_dict = _serialize_user_profile(profile), _serialize_lab_report(report)
#         targets_dict = _calculate_target_nutrients(profile_dict)

#         legacy_plan_json = {}
#         used_foods = set()
        
#         for day_num in range(1, 16): # Loop from Day 1 to 15
#             print(f"Generating structured plan for Day {day_num}...")
#             # Calls the correct helper function for structured data
#             daily_plan = _call_gemini_for_single_day_structured(profile_dict, targets_dict, day_num, used_foods)
#             if daily_plan.get("error") == "AI_QUOTA_EXCEEDED":
#                 return None, (
#                     "AI service quota exceeded. "
#                     "Please try again after some time."
#                 )
#             if "error" in daily_plan:
#                 return None, f"AI generation failed on Day {day_num}: {daily_plan['error']}"

#             legacy_plan_json[f"Day {day_num}"] = daily_plan
            
#             for meal in daily_plan.values():
#                 used_foods.add(meal.get("food_name"))
            
#             sleep(1) # Small delay to avoid API rate limits
        
#         print("Generating suggestion flags...")
#         flags = _call_gemini_for_flags(profile_dict, report_dict)
#         legacy_plan_json["suggestion_flags"] = flags

#         full_snapshot = {"profile": profile_dict, "lab_report": report_dict, "targets": targets_dict}
#         # new_plan = DietRecommendation.objects.create(
#         #     user=patient, for_week_starting=timezone.now().date(), meals=legacy_plan_json,
#         #     original_ai_plan=legacy_plan_json, user_profile_snapshot=full_snapshot, status='pending',
#         #     reviewed_by=nutritionist, nutritionist_comment="Plan generated by nutritionist."
#         # )
#         # return new_plan, None
#         return legacy_plan_json, None

#     except (User.DoesNotExist, UserProfile.DoesNotExist, ValueError) as e:
#         return None, str(e)
#     except Exception as e:
#         traceback.print_exc()
#         return None, f"An unexpected server error occurred: {e}"

# ==============================================================================
# Diet Plan Generation Service (PRODUCTION-SAFE VERSION)
# ==============================================================================

# import json
# import traceback
# import time
# from datetime import date, datetime
# from time import sleep

# import google.generativeai as genai
# from google.api_core.exceptions import DeadlineExceeded

# from django.db import transaction
# from django.contrib.auth import get_user_model
# from django.utils import timezone

# from userProfile.models import UserProfile, LabReport
# from diet.models import DietRecommendation

# import os
# import dotenv
# dotenv.load_dotenv()

# # ==============================================================================
# # CONFIG
# # ==============================================================================

# API_KEY = os.getenv("GEMINI_API_KEY")
# if API_KEY:
#     genai.configure(api_key=API_KEY)

# TOTAL_DAYS = 7
# MIN_DAYS_REQUIRED = 3
# GEMINI_TIMEOUT = 120
# MAX_RETRIES = 3

# MEAL_SLOTS = [
#     "Early-Morning",
#     "Breakfast",
#     "Mid-Morning Snack",
#     "Lunch",
#     "Afternoon Snack",
#     "Dinner",
#     "Bedtime",
# ]

# REQUIRED_MEAL_KEYS = {
#     "food_name",
#     "Calories",
#     "Protein_g",
#     "Carbs_g",
#     "Fats_g",
#     "Gram_Equivalent",
# }

# # ==============================================================================
# # SERIALIZERS
# # ==============================================================================

# def _serialize_user_profile(profile: UserProfile) -> dict:
#     return {
#         "date_of_birth": profile.date_of_birth.strftime("%Y-%m-%d") if profile.date_of_birth else None,
#         "gender": profile.gender,
#         "height_cm": profile.height_cm,
#         "weight_kg": profile.weight_kg,
#         "activity_level": profile.activity_level,
#         "goal": profile.goal,
#         "diet_type": profile.diet_type,
#         "allergies": profile.allergies,
#         "is_diabetic": profile.is_diabetic,
#     }


# def _serialize_lab_report(report: LabReport | None) -> dict:
#     if not report:
#         return {}
#     return {
#         "fasting_blood_sugar": report.fasting_blood_sugar,
#         "hba1c": report.hba1c,
#         "ldl_cholesterol": report.ldl_cholesterol,
#         "hdl_cholesterol": report.hdl_cholesterol,
#         "triglycerides": report.triglycerides,
#     }

# # ==============================================================================
# # NUTRIENT TARGETS
# # ==============================================================================

# def _calculate_target_nutrients(profile: dict) -> dict:
#     today = date.today()
#     dob = datetime.strptime(profile["date_of_birth"], "%Y-%m-%d").date()
#     age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

#     w = profile["weight_kg"]
#     h = profile["height_cm"]
#     g = profile["gender"].lower()
#     act = profile["activity_level"].lower()
#     goal = profile["goal"].lower()

#     bmr = 10 * w + 6.25 * h - 5 * age + (5 if g == "male" else -161)
#     multiplier = {
#         "sedentary": 1.2,
#         "lightly active": 1.375,
#         "moderately active": 1.55,
#     }.get(act, 1.2)

#     calories = bmr * multiplier
#     if "gain" in goal:
#         calories += 400
#     elif "lose" in goal:
#         calories -= 500

#     return {
#         "calories": round(calories),
#         "protein_g": round(w * 1.8),
#         "fats_g": round(w * 0.8),
#         "carbs_g": round((calories - (w * 1.8 * 4 + w * 0.8 * 9)) / 4),
#     }

# # ==============================================================================
# # GEMINI CALL
# # ==============================================================================

# def _call_gemini(profile, targets, day_number, used_foods):
#     if not API_KEY:
#         return {"error": "GEMINI_API_KEY missing"}

#     avoid_foods = ", ".join(sorted(used_foods)) if used_foods else "None"

#     prompt = f"""
#     Generate Day {day_number} meal plan.

#     User: {json.dumps(profile)}
#     Targets: {json.dumps(targets)}

#     RULES:
#     - Output MUST be JSON OBJECT
#     - Keys must be exactly:
#       {MEAL_SLOTS}
#     - Each meal must contain:
#       food_name, Calories, Protein_g, Carbs_g, Fats_g, Gram_Equivalent
#     - Do NOT return a list

#     Avoid foods: {avoid_foods}
#     """

#     model = genai.GenerativeModel("gemini-2.5-flash")
#     config = genai.types.GenerationConfig(
#         temperature=0.4,
#         response_mime_type="application/json",
#     )

#     for attempt in range(1, MAX_RETRIES + 1):
#         try:
#             response = model.generate_content(
#                 prompt,
#                 generation_config=config,
#                 request_options={"timeout": GEMINI_TIMEOUT},
#             )
#             return json.loads(response.text)

#         except DeadlineExceeded:
#             print(f"⏱️ Timeout Day {day_number}, retry {attempt}")
#             time.sleep(3)

#         except Exception:
#             traceback.print_exc()
#             return {"error": "Gemini failure"}

#     return {"error": "Gemini timeout"}

# # ==============================================================================
# # MAIN SERVICE
# # ==============================================================================

# @transaction.atomic
# def generate_ai_plan_for_patient(patient_id: int, nutritionist_id: int):
#     User = get_user_model()

#     patient = User.objects.get(id=patient_id, role="user")
#     nutritionist = User.objects.get(id=nutritionist_id)

#     profile = UserProfile.objects.get(user=patient)
#     report = LabReport.objects.filter(user=patient).order_by("-report_date").first()

#     profile_dict = _serialize_user_profile(profile)
#     targets = _calculate_target_nutrients(profile_dict)

#     final_meals = {}
#     used_foods = set()
#     week_start = timezone.now().date()

#     for day in range(1, TOTAL_DAYS + 1):
#         print(f"Generating structured plan for Day {day}...")

#         daily_plan = _call_gemini(profile_dict, targets, day, used_foods)

#         if "error" in daily_plan:
#             print(f"⚠️ Skipping Day {day}")
#             continue

#         # 🔒 NORMALIZE (GUARD AGAINST LIST)
#         if isinstance(daily_plan, list):
#             daily_plan = {
#                 MEAL_SLOTS[i]: meal
#                 for i, meal in enumerate(daily_plan)
#                 if i < len(MEAL_SLOTS)
#             }

#         if not isinstance(daily_plan, dict):
#             raise ValueError(f"Invalid Gemini response for Day {day}")

#         # ✅ VALIDATE
#         normalized_day = {}
#         for slot in MEAL_SLOTS:
#             meal = daily_plan.get(slot)
#             if not isinstance(meal, dict):
#                 raise ValueError(f"Missing {slot} on Day {day}")

#             missing = REQUIRED_MEAL_KEYS - meal.keys()
#             if missing:
#                 raise ValueError(f"Day {day} {slot} missing {missing}")

#             food = meal["food_name"].strip()
#             used_foods.add(food)
#             normalized_day[slot] = meal

#         final_meals[f"Day {day}"] = normalized_day

#         # 💾 SAVE PROGRESS
#         DietRecommendation.objects.update_or_create(
#             user=patient,
#             for_week_starting=week_start,
#             defaults={
#                 "meals": final_meals,
#                 "original_ai_plan": final_meals,
#                 "status": "pending",
#                 "reviewed_by": nutritionist,
#             },
#         )

#         sleep(1)

#     if len(final_meals) < MIN_DAYS_REQUIRED:
#         raise ValueError("Insufficient valid days generated")

#     plan = DietRecommendation.objects.filter(
#         user=patient,
#         for_week_starting=week_start
#     ).first()

#     plan.user_profile_snapshot = {
#         "profile": profile_dict,
#         "targets": targets,
#     }
#     plan.save(update_fields=["user_profile_snapshot"])

#     return plan, None
