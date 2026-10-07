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
    """Calculates nutritional targets using canonical engine."""
    from utils.utils import calculate_target_nutrients
    return calculate_target_nutrients(data)


def _normalize_plan_to_target(plan_json: dict, target_calories: float) -> dict:
    """
    Guarantees that the sum of calories for each day (Day 1, Day 2, Day 3)
    accurately matches target_calories within 0-1 kcal, scaling macros proportionally.
    """
    if not isinstance(plan_json, dict) or not target_calories or target_calories <= 0:
        return plan_json

    target_calories = float(target_calories)

    for day_key in ["Day 1", "Day 2", "Day 3"]:
        day_meals = plan_json.get(day_key)
        if not isinstance(day_meals, dict):
            continue

        meal_keys = []
        day_total_cal = 0.0
        for m_name, m_data in day_meals.items():
            if isinstance(m_data, dict) and "Calories" in m_data:
                day_total_cal += float(m_data.get("Calories") or 0)
                meal_keys.append(m_name)

        if day_total_cal <= 0 or not meal_keys:
            continue

        ratio = target_calories / day_total_cal
        # Scale if within a sensible range (0.5 to 2.0)
        if 0.5 <= ratio <= 2.0:
            running_cal = 0
            for idx, m_name in enumerate(meal_keys):
                m = day_meals[m_name]
                if not isinstance(m, dict):
                    continue

                if idx == len(meal_keys) - 1:
                    new_cal = max(10, round(target_calories - running_cal))
                else:
                    new_cal = max(10, round(float(m.get("Calories") or 0) * ratio))
                    running_cal += new_cal

                m["Calories"] = new_cal
                if m.get("Protein") is not None:
                    m["Protein"] = round(float(m["Protein"]) * ratio, 1)
                if m.get("Carbs") is not None:
                    m["Carbs"] = round(float(m["Carbs"]) * ratio, 1)
                if m.get("Fats") is not None:
                    m["Fats"] = round(float(m["Fats"]) * ratio, 1)
                if m.get("Sugar") is not None:
                    m["Sugar"] = round(float(m["Sugar"]) * ratio, 1)
                if m.get("Fiber") is not None:
                    m["Fiber"] = round(float(m["Fiber"]) * ratio, 1)
                if m.get("Gram_Equivalent") is not None:
                    m["Gram_Equivalent"] = round(float(m["Gram_Equivalent"]) * ratio)

    return plan_json


def generate_ai_plan_for_patient(profile_dict, report_dict, targets_dict):
    """
    PURE AI FUNCTION.
    Generates the complete 3-day meal plan and suggestion flags in ONE single Gemini API call.
    Strictly adheres to the patient's daily target calories and macronutrients.
    No Django ORM.
    No DB access.
    No connection handling.
    """
    try:
        if not API_KEY:
            return None, "GEMINI_API_KEY is not configured."

        rec_cals = round(float(targets_dict.get("recommended_calories") or 2000))
        macros = targets_dict.get("macronutrients", {})
        protein_g = round(float(targets_dict.get("protein_g") or macros.get("protein_g") or 75))
        carbs_g = round(float(targets_dict.get("carbs_g") or macros.get("carbs_g") or 250))
        fats_g = round(float(targets_dict.get("fats_g") or macros.get("fats_g") or 55))
        fiber_g = round(float(targets_dict.get("fiber_g") or macros.get("fiber_g") or 30))

        # Caloric budget breakdown for meals
        early_cals = round(rec_cals * 0.05)
        breakfast_cals = round(rec_cals * 0.25)
        midmorning_cals = round(rec_cals * 0.10)
        lunch_cals = round(rec_cals * 0.30)
        afternoon_cals = round(rec_cals * 0.10)
        dinner_cals = round(rec_cals * 0.15)
        bedtime_cals = round(rec_cals * 0.05)

        prompt = f"""
You are an expert clinical dietitian generating a complete, culturally accurate 3-day meal plan (Day 1, Day 2, Day 3) and 4 concise clinical suggestions for a patient.

User Health Profile:
{json.dumps(profile_dict)}

Lab Report Biomarkers (if available):
{json.dumps(report_dict)}

MANDATORY DAILY TARGETS:
- Target Daily Calories: {rec_cals} kcal per day (Day 1, Day 2, Day 3 MUST each sum up to {rec_cals} kcal ±3%)
- Target Daily Protein: {protein_g}g
- Target Daily Carbs: {carbs_g}g
- Target Daily Fats: {fats_g}g
- Target Daily Fiber: {fiber_g}g

SUGGESTED DAILY CALORIC BUDGET DISTRIBUTION:
- Early-Morning: ~{early_cals} kcal (warm herbal tea, soaked nuts/seeds, water)
- Breakfast: ~{breakfast_cals} kcal (nutrient-dense, substantial breakfast)
- Mid-Morning Snack: ~{midmorning_cals} kcal (fruits, coconut water, or sprouts)
- Lunch: ~{lunch_cals} kcal (main balanced meal with whole grains, lean protein, vegetables)
- Afternoon Snack: ~{afternoon_cals} kcal (makhana, roasted chana, green tea, or nuts)
- Dinner: ~{dinner_cals} kcal (digestible wholesome dinner)
- Bedtime: ~{bedtime_cals} kcal (warm turmeric/herbal milk)

--- GUIDELINES ---
1. STRICT CALORIE ALIGNMENT (CRITICAL): The sum of Calories for all 7 meals in each day (Day 1, Day 2, Day 3) MUST add up to the daily target of {rec_cals} kcal (±3%). Adjust dish portion sizes (grams, bowls, spoons) so that total calories and macronutrients strictly adhere to this target.
2. Food Culture & Region: Strictly align dishes with Country: {profile_dict.get("country", "Not specified")} and City: {profile_dict.get("city", "Not specified")}. Use staple local carbs, oils, vegetables, and proteins.
3. Realistic Household Portions & Grams (CRITICAL): Every meal item MUST specify intuitive household serving measures (e.g., small/medium bowl / katori, cup, tbsp/tsp, glass, number of rotis/eggs) combined with exact gram/ml equivalents in parentheses.
   - Required format examples:
     * "1 Small Bowl Dal Tadka (200g) with 1 Bowl Jeera Rice (200g) and 2 tbsp Mixed Veg Sabzi (150g)"
     * "2 Medium Rotis (60g) with 1 Medium Bowl Palak Paneer (150g) and 1 Small Cup Cucumber Raita (100g)"
     * "1 Bowl Oats Porridge (180g) with 1 tbsp Chia Seeds (10g) and 1/2 Sliced Apple (60g)"
     * "1 Glass Warm Turmeric Milk (200ml) with 4 Soaked Almonds (10g)"
4. Complete Nutrition: Provide exact numeric `Gram_Equivalent`, `Calories`, `Protein`, `Carbs`, `Fats`, `Sugar`, and `Fiber` for every meal.
5. Suggestions: 4 concise cards (1-2 sentences each) for "avoid" (Foods to Avoid), "follow" (Foods to Follow), "exercise" (Exercise & Activity), and "lifestyle" (Lifestyle & Hydration).
6. Output ONLY valid JSON matching this schema.

--- JSON SCHEMA REQUIRED ---
{{
  "Day 1": {{
    "Early-Morning": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '1 Glass Warm Turmeric Milk (200ml) with 4 Soaked Almonds (10g)'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Breakfast": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '1 Bowl Oats Porridge (180g) with 1 tbsp Chia Seeds (10g) and 1/2 Sliced Apple (60g)'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Mid-Morning Snack": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '1 Glass Tender Coconut Water (250ml) with 1 Small Bowl Sprouted Moong (120g)'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Lunch": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '1 Small Bowl Dal Tadka (200g) with 1 Bowl Jeera Rice (200g) and 2 tbsp Mixed Veg Sabzi (150g)'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Afternoon Snack": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '1 Medium Bowl Roasted Chana (60g) with 1 Medium Banana (100g)'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Dinner": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '2 Medium Rotis (60g) with 1 Medium Bowl Palak Paneer (150g) and 1 Small Cup Cucumber Raita (100g)'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Bedtime": {{ "food_name": "<Full descriptive meal WITH household units and grams, e.g. '1 Glass Warm Turmeric Milk (250ml) with Pinch of Cardamom'>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }}
  }},
  "Day 2": {{
    "Early-Morning": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Breakfast": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Mid-Morning Snack": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Lunch": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Afternoon Snack": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Dinner": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Bedtime": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }}
  }},
  "Day 3": {{
    "Early-Morning": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Breakfast": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Mid-Morning Snack": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Lunch": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Afternoon Snack": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Dinner": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }},
    "Bedtime": {{ "food_name": "<Full descriptive meal WITH household units and grams>", "quantity": "<str>", "Gram_Equivalent": <float>, "Calories": <float>, "Protein": <float>, "Carbs": <float>, "Fats": <float>, "Sugar": <float>, "Fiber": <float> }}
  }},
  "suggestions": [
    {{
      "id": "sug_1",
      "key": "avoid",
      "category": "Foods to Avoid",
      "title": "<Short title, max 6 words>",
      "description": "<Concise 1-2 sentence actionable avoidance guidance>"
    }},
    {{
      "id": "sug_2",
      "key": "follow",
      "category": "Foods to Follow",
      "title": "<Short title, max 6 words>",
      "description": "<Concise 1-2 sentence actionable foods to include>"
    }},
    {{
      "id": "sug_3",
      "key": "exercise",
      "category": "Exercise & Activity",
      "title": "<Short title, max 6 words>",
      "description": "<Concise 1-2 sentence actionable workout routine>"
    }},
    {{
      "id": "sug_4",
      "key": "lifestyle",
      "category": "Lifestyle & Hydration",
      "title": "<Short title, max 6 words>",
      "description": "<Concise 1-2 sentence actionable lifestyle/hydration tip>"
    }}
  ],
  "suggestion_flags": ["<flag1>", "<flag2>"]
}}
"""
        models_to_try = ["gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-flash-latest"]
        full_plan_json = None
        config = genai.types.GenerationConfig(temperature=0.3, response_mime_type="application/json")

        for m_name in models_to_try:
            try:
                print(f"Generating complete 3-day plan + suggestions via model {m_name}...")
                model = genai.GenerativeModel(model_name=m_name)
                response = model.generate_content(prompt, generation_config=config)
                if response and response.text:
                    clean_text = response.text.replace("```json", "").replace("```", "").strip()
                    full_plan_json = json.loads(clean_text)
                    if full_plan_json and ("Day 1" in full_plan_json or "suggestions" in full_plan_json):
                        print(f"✅ Successfully generated plan with {m_name}")
                        break
            except Exception as m_err:
                print(f"Model {m_name} failed: {m_err}")
                continue

        if not full_plan_json:
            return None, "Failed to generate plan from AI models."

        # Guarantee that food_name ALWAYS contains the full household units and grams
        for day_k in ["Day 1", "Day 2", "Day 3"]:
            day_dict = full_plan_json.get(day_k)
            if isinstance(day_dict, dict):
                for slot_k, slot_v in day_dict.items():
                    if isinstance(slot_v, dict):
                        qty = str(slot_v.get("quantity") or "").strip()
                        fname = str(slot_v.get("food_name") or "").strip()
                        has_qty_units = any(u in qty.lower() for u in ["bowl", "katori", "cup", "tbsp", "tsp", "roti", "glass", "g)", "ml)"])
                        has_fname_units = any(u in fname.lower() for u in ["bowl", "katori", "cup", "tbsp", "tsp", "roti", "glass", "g)", "ml)"])
                        if has_qty_units and not has_fname_units:
                            slot_v["food_name"] = qty

        # Normalize generated plan meals to strictly adhere to target calories
        full_plan_json = _normalize_plan_to_target(full_plan_json, rec_cals)

        if "suggestion_flags" not in full_plan_json or not isinstance(full_plan_json["suggestion_flags"], list):
            full_plan_json["suggestion_flags"] = []

        if "suggestions" not in full_plan_json or not isinstance(full_plan_json["suggestions"], list):
            full_plan_json["suggestions"] = []

        return full_plan_json, None

    except ResourceExhausted:
        return None, "AI quota exceeded. Try later."
    except Exception as e:
        traceback.print_exc()
        return None, str(e)


def calculate_single_meal_nutrition_gemini(food_query: str, meal_context: dict = None) -> dict | None:
    """
    Sends an individual edited meal item to Gemini to parse its portions/ingredients
    and compute its complete, accurate nutritional values (Calories, Macros, Grams, Quantity).
    Returns a standardized dictionary ready to plug directly into recommendation.meals[day][slot].
    """
    if not food_query or not food_query.strip():
        return None

    clean_query = food_query.strip()
    if not API_KEY:
        return None

    prompt = f"""
You are an expert clinical nutrition analysis AI.
The dietitian has updated a meal item in the patient's diet plan to: "{clean_query}".

Analyze this food item, identify the exact portion/weight/volume, and calculate the COMPLETE nutritional values for this exact serving.
If the meal description mentions household measures (like bowls, cups, spoons, rotis) and/or grams, accurately reflect both in the clean `food_name` and `quantity`.

Return a single JSON object with the following fields:
{{
  "food_name": "<Clean, descriptive name with household measures and gram equivalents, e.g. '1 Small Bowl Dal Tadka (200g) with 1 Bowl Jeera Rice (200g) and 2 tbsp Veg Sabzi (150g)'>",
  "quantity": "<Short portion description, e.g. '1 small bowl dal (200g), 1 bowl rice (200g), 2 tbsp sabzi (150g)'>",
  "Gram_Equivalent": <float, total weight in grams>,
  "Calories": <float, total calories in kcal>,
  "Protein": <float, total protein in grams>,
  "Carbs": <float, total carbohydrates in grams>,
  "Fats": <float, total fats in grams>,
  "Sugar": <float, total sugar in grams>,
  "Fiber": <float, total dietary fiber in grams>
}}

CRITICAL RULES:
- Calculate calories and macros accurately based on USDA / standard food database data for the specified ingredients and portions.
- Every numeric value MUST be an accurate numeric float or int (never null, never string).
- Return ONLY valid JSON matching the schema above.
"""
    models_to_try = ["gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-flash-latest"]
    config = genai.types.GenerationConfig(temperature=0.1, response_mime_type="application/json")

    for m_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name=m_name)
            response = model.generate_content(prompt, generation_config=config)
            if response and response.text:
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_text)
                if isinstance(data, dict) and "Calories" in data:
                    return {
                        "food_name": str(data.get("food_name") or clean_query).strip(),
                        "quantity": str(data.get("quantity") or clean_query).strip(),
                        "Gram_Equivalent": float(data.get("Gram_Equivalent") or 100.0),
                        "Calories": round(float(data.get("Calories") or 0.0), 1),
                        "Protein": round(float(data.get("Protein") or 0.0), 1),
                        "Carbs": round(float(data.get("Carbs") or 0.0), 1),
                        "Fats": round(float(data.get("Fats") or 0.0), 1),
                        "Sugar": round(float(data.get("Sugar") or 0.0), 1),
                        "Fiber": round(float(data.get("Fiber") or 0.0), 1),
                    }
        except Exception as err:
            print(f"Model {m_name} failed for meal '{clean_query}': {err}")
            continue

    return None


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
