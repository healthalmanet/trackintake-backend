# import logging
# from django.utils import timezone
# from django.db.models import Sum, Q

# logger = logging.getLogger(__name__)

# # ── Country → cuisine keyword map ────────────────────────────────
# COUNTRY_CUISINE_MAP = {
#     "india":      ["paneer", "dal", "roti", "sabzi", "rice", "idli", "dosa",
#                    "paratha", "khichdi", "sambar", "curry", "chapati", "raita",
#                    "poha", "upma", "uttapam", "biryani", "pulao", "chole",
#                    "rajma", "kadhi", "halwa", "lassi"],
#     "usa":        ["oatmeal", "sandwich", "salad", "wrap", "quinoa", "smoothie",
#                    "granola", "eggs", "avocado", "bagel", "turkey", "chicken breast"],
#     "uk":         ["porridge", "beans", "toast", "salad", "soup", "sandwich"],
#     "pakistan":   ["roti", "dal", "curry", "biryani", "nihari", "haleem", "paratha"],
#     "bangladesh": ["rice", "dal", "fish", "curry", "hilsa", "bhaji"],
#     "sri lanka":  ["rice", "curry", "hoppers", "kottu", "sambal", "dhal"],
#     "nepal":      ["dal bhat", "momo", "thukpa", "tarkari"],
#     "china":      ["tofu", "noodles", "fried rice", "dumpling", "congee"],
#     "japan":      ["tofu", "miso", "edamame", "rice", "soba", "salmon"],
#     "italy":      ["pasta", "salad", "soup", "risotto", "bruschetta"],
#     "mexico":     ["beans", "tortilla", "avocado", "quinoa", "salsa"],
#     "thailand":   ["rice", "tofu", "papaya", "curry", "noodles"],
# }

# GOAL_STRATEGY = {
#     "lose weight":     {"calorie_factor": 0.50, "protein_priority": True},
#     "maintain weight": {"calorie_factor": 0.60, "protein_priority": False},
#     "gain weight":     {"calorie_factor": 0.70, "protein_priority": True},
# }


# # ────────────────────────────────────────────────────────────────
# # HELPERS
# # ────────────────────────────────────────────────────────────────

# def _get_country_keywords(country: str) -> list:
#     return COUNTRY_CUISINE_MAP.get(country.lower().strip(), []) if country else []


# def _food_matches_country(food_name: str, keywords: list) -> bool:
#     if not keywords:
#         return True
#     return any(kw in food_name.lower() for kw in keywords)


# def _get_diet_type_q(diet_type: str) -> Q:
#     dt = (diet_type or "").lower().strip()
#     if dt in ("vegetarian", "vegan", "eggetarian"):
#         return ~Q(food_types__name__icontains="Non-Vegetarian")
#     return Q()


# # ────────────────────────────────────────────────────────────────
# # LAB REPORT READER
# # ────────────────────────────────────────────────────────────────

# def _get_latest_lab_data(user) -> dict:
#     """
#     Reads the most recent LabReport for the user.
#     Returns a flat dict of clinically relevant values.
#     All values are None if no report exists.
#     """
#     try:
#         from userProfile.models import LabReport
#         report = LabReport.objects.filter(user=user).order_by("-report_date").first()
#         if not report:
#             return {}
#         return {
#             "hba1c":                   report.hba1c,
#             "fasting_blood_sugar":     report.fasting_blood_sugar,
#             "postprandial_sugar":      report.postprandial_sugar,
#             "ldl_cholesterol":         report.ldl_cholesterol,
#             "hdl_cholesterol":         report.hdl_cholesterol,
#             "triglycerides":           report.triglycerides,
#             "blood_pressure_systolic": report.blood_pressure_systolic,
#             "uric_acid":               report.uric_acid,
#             "crp":                     report.crp,
#             "vitamin_d3":              report.vitamin_d3,
#             "vitamin_b12":             report.vitamin_b12,
#             "tsh":                     report.tsh,
#             "creatinine":              report.creatinine,
#         }
#     except Exception as exc:
#         logger.warning(f"Lab report fetch failed: {exc}")
#         return {}


# def _derive_conditions_from_labs(lab: dict, profile) -> dict:
#     """
#     Derives or confirms medical conditions from lab values.
#     Lab data overrides/supplements profile boolean flags.
#     Returns a conditions dict used throughout scoring.
#     """
#     # Start from profile boolean flags
#     is_diabetic     = bool(getattr(profile, "is_diabetic",        False))
#     is_hypertensive = bool(getattr(profile, "is_hypertensive",    False))
#     has_heart       = bool(getattr(profile, "has_heart_condition", False))
#     has_arthritis   = bool(getattr(profile, "has_arthritis",       False))
#     has_gastric     = bool(getattr(profile, "has_gastric_issues",  False))
#     has_thyroid     = bool(getattr(profile, "has_thyroid_disorder",False))

#     # Upgrade flags from lab values if available
#     if lab.get("hba1c") and lab["hba1c"] >= 6.5:
#         is_diabetic = True          # HbA1c ≥ 6.5% → confirmed diabetes
#     elif lab.get("fasting_blood_sugar") and lab["fasting_blood_sugar"] >= 126:
#         is_diabetic = True          # FBS ≥ 126 mg/dL → diabetes

#     if lab.get("blood_pressure_systolic") and lab["blood_pressure_systolic"] >= 140:
#         is_hypertensive = True      # Systolic ≥ 140 mmHg → hypertension

#     if lab.get("ldl_cholesterol") and lab["ldl_cholesterol"] >= 160:
#         has_heart = True            # High LDL → elevated cardiovascular risk
#     if lab.get("triglycerides") and lab["triglycerides"] >= 200:
#         has_heart = True            # High TGs → elevated cardiovascular risk

#     if lab.get("uric_acid") and lab["uric_acid"] >= 7.0:
#         has_arthritis = True        # High uric acid → gout risk

#     # Blood sugar control level (for granular diabetic scoring)
#     sugar_controlled = True
#     if lab.get("hba1c"):
#         sugar_controlled = lab["hba1c"] < 7.0
#     elif lab.get("fasting_blood_sugar"):
#         sugar_controlled = lab["fasting_blood_sugar"] < 130

#     # Vitamin deficiencies
#     low_vitamin_d  = lab.get("vitamin_d3")  is not None and lab["vitamin_d3"]  < 20
#     low_vitamin_b12= lab.get("vitamin_b12") is not None and lab["vitamin_b12"] < 200
#     low_hdl        = lab.get("hdl_cholesterol") is not None and lab["hdl_cholesterol"] < 40

#     return {
#         "is_diabetic":       is_diabetic,
#         "is_hypertensive":   is_hypertensive,
#         "has_heart":         has_heart,
#         "has_arthritis":     has_arthritis,
#         "has_gastric":       has_gastric,
#         "has_thyroid":       has_thyroid,
#         "sugar_controlled":  sugar_controlled,
#         "low_vitamin_d":     low_vitamin_d,
#         "low_vitamin_b12":   low_vitamin_b12,
#         "low_hdl":           low_hdl,
#         # Raw lab values for scoring
#         "hba1c":             lab.get("hba1c"),
#         "fasting_sugar":     lab.get("fasting_blood_sugar"),
#         "ldl":               lab.get("ldl_cholesterol"),
#         "triglycerides":     lab.get("triglycerides"),
#         "uric_acid":         lab.get("uric_acid"),
#     }


# # ────────────────────────────────────────────────────────────────
# # NUTRIENT CALCULATIONS
# # ────────────────────────────────────────────────────────────────

# def get_today_consumed(user) -> dict:
#     from userFood.models import UserMeal
#     today = timezone.now().date()
#     agg = UserMeal.objects.filter(user=user, date=today).aggregate(
#         calories=Sum("calories"),
#         protein=Sum("protein"),
#         carbs=Sum("carbs"),
#         fats=Sum("fats"),
#         sugar=Sum("sugar"),
#         fiber=Sum("fiber"),
#     )
#     return {k: round(v or 0, 2) for k, v in agg.items()}


# def get_remaining_nutrients(user) -> dict:
#     """
#     Uses the same get_target_nutrients() as the dashboard
#     so calorie targets are always consistent.
#     """
#     from utils.utils import get_target_nutrients
#     from userFood.models import UserMeal

#     today   = timezone.now().date()
#     targets = get_target_nutrients(user)

#     cal_target     = targets.get("recommended_calories", 2000)
#     protein_target = targets.get("macronutrients", {}).get("protein_g", 50)
#     carbs_target   = targets.get("macronutrients", {}).get("carbs_g", 250)
#     fats_target    = targets.get("macronutrients", {}).get("fats_g", 65)
#     sugar_target   = targets.get("macronutrients", {}).get("sugar_g", 28)
#     fiber_target   = targets.get("macronutrients", {}).get("fiber_g", 25)

#     meals = UserMeal.objects.filter(user=user, date=today)
#     consumed = {
#         "calories": float(meals.aggregate(v=Sum("calories"))["v"] or 0),
#         "protein":  float(meals.aggregate(v=Sum("protein"))["v"]  or 0),
#         "carbs":    float(meals.aggregate(v=Sum("carbs"))["v"]    or 0),
#         "fats":     float(meals.aggregate(v=Sum("fats"))["v"]     or 0),
#         "sugar":    float(meals.aggregate(v=Sum("sugar"))["v"]    or 0),
#         "fiber":    float(meals.aggregate(v=Sum("fiber"))["v"]    or 0),
#     }

#     pct = round((consumed["calories"] / cal_target * 100), 1) if cal_target else 0

#     return {
#         "remaining": {
#             "calories":  max(0, round(cal_target     - consumed["calories"], 1)),
#             "protein_g": max(0, round(protein_target - consumed["protein"],  2)),
#             "carbs_g":   max(0, round(carbs_target   - consumed["carbs"],    2)),
#             "fats_g":    max(0, round(fats_target    - consumed["fats"],     2)),
#             "sugar_g":   max(0, round(sugar_target   - consumed["sugar"],    2)),
#             "fiber_g":   max(0, round(fiber_target   - consumed["fiber"],    2)),
#         },
#         "consumed": consumed,
#         "targets": {
#             "calories":  cal_target,
#             "protein_g": protein_target,
#             "carbs_g":   carbs_target,
#             "fats_g":    fats_target,
#             "sugar_g":   sugar_target,
#             "fiber_g":   fiber_target,
#         },
#         "goal":             targets.get("weight_target", {}).get("goal", "Maintain Weight"),
#         "pct_cal_consumed": pct,
#     }


# # ────────────────────────────────────────────────────────────────
# # SCORING  (medical history fully integrated)
# # ────────────────────────────────────────────────────────────────

# def _score_food(food, remaining, goal, country_keywords, conditions, from_plan=False):
#     """
#     Scores a food item against the user's remaining macros and medical profile.

#     conditions dict (from _derive_conditions_from_labs):
#       is_diabetic, is_hypertensive, has_heart, has_arthritis,
#       has_gastric, has_thyroid, sugar_controlled, low_vitamin_d,
#       low_vitamin_b12, low_hdl, hba1c, fasting_sugar, ldl, triglycerides, uric_acid
#     """
#     score = 0; reasons = []; warnings = []; fills_gap = {}

#     rem_cal  = remaining["calories"]
#     rem_prot = remaining["protein_g"]
#     rem_sugar= remaining["sugar_g"]
#     rem_fiber= remaining["fiber_g"]
#     strategy = GOAL_STRATEGY.get(goal.lower(), GOAL_STRATEGY["maintain weight"])

#     # ── 1. Calorie fit (30 pts) ───────────────────────────────────
#     ideal_cal = rem_cal * strategy["calorie_factor"]
#     if ideal_cal > 0 and food.calories and food.calories > 0:
#         diff  = abs(food.calories - ideal_cal) / ideal_cal
#         score += max(0, 30 * (1 - diff))
#         if diff < 0.25:
#             reasons.append(
#                 f"Right portion · {food.calories:.0f} kcal fits your remaining {rem_cal:.0f} kcal"
#             )
#             fills_gap["calories"] = f"{food.calories:.0f} of {rem_cal:.0f} kcal remaining"

#     # ── 2. Protein gap fill (40 pts) ─────────────────────────────
#     if rem_prot > 0 and food.protein and food.protein > 0:
#         ratio = food.protein / rem_prot
#         score += min(40, ratio * 40)
#         pct   = round(ratio * 100, 1)
#         if pct >= 10:
#             reasons.append(f"High protein · fills {pct}% of your {rem_prot:.0f}g gap")
#             fills_gap["protein"] = f"{food.protein:.1f}g of {rem_prot:.0f}g remaining"

#     # ── 3. Diet plan bonus (20 pts) ──────────────────────────────
#     if from_plan:
#         score += 20
#         reasons.append("Matches your nutritionist plan")

#     # ── 4. Regional cuisine (10 pts) ─────────────────────────────
#     if country_keywords and _food_matches_country(food.name, country_keywords):
#         score += 10
#         reasons.append("Suits your regional cuisine")

#     # ── 5. DIABETES scoring ──────────────────────────────────────
#     if conditions.get("is_diabetic"):
#         gi = food.estimated_gi
#         sugar = food.sugar or 0

#         if gi:
#             if gi < 40:
#                 score += 10
#                 reasons.append(f"Very low GI ({gi:.0f}) · excellent for blood sugar control")
#             elif gi < 55:
#                 score += 6
#                 reasons.append(f"Low GI ({gi:.0f}) · good for blood sugar")
#             elif gi >= 70:
#                 score -= 10
#                 warnings.append("High GI · may spike blood sugar ⚠️")

#         if sugar < 5:
#             score += 5
#             reasons.append(f"Low sugar · {sugar:.1f}g per serving")
#         elif sugar > 15:
#             score -= 8
#             warnings.append(f"High sugar ({sugar:.1f}g) · avoid if blood sugar is uncontrolled")

#         # Fiber helps blood sugar — extra weight for diabetics
#         if food.fiber and food.fiber >= 5:
#             score += 5
#             reasons.append(f"High fiber ({food.fiber:.1f}g) · slows sugar absorption")

#         # If poorly controlled diabetes, be stricter
#         if not conditions.get("sugar_controlled"):
#             if gi and gi >= 55:
#                 score -= 5
#             if sugar > 10:
#                 score -= 5

#     # ── 6. HYPERTENSION scoring ──────────────────────────────────
#     if conditions.get("is_hypertensive"):
#         sodium = food.sodium_mg or 0
#         potassium = food.potassium_mg or 0

#         if sodium < 140:
#             score += 8
#             reasons.append(f"Very low sodium ({sodium:.0f}mg) · excellent for blood pressure")
#         elif sodium < 300:
#             score += 4
#             reasons.append("Low sodium · heart-friendly")
#         elif sodium > 600:
#             score -= 10
#             warnings.append(f"High sodium ({sodium:.0f}mg) · avoid with hypertension ⚠️")

#         if potassium > 400:
#             score += 4
#             reasons.append(f"High potassium ({potassium:.0f}mg) · helps lower blood pressure")

#     # ── 7. HEART CONDITION scoring ───────────────────────────────
#     if conditions.get("has_heart"):
#         sat_fat = food.saturated_fat_g or 0
#         omega3  = food.omega_3_g or 0

#         if sat_fat < 2:
#             score += 6
#             reasons.append("Low saturated fat · heart-safe")
#         elif sat_fat > 5:
#             score -= 8
#             warnings.append(f"High saturated fat ({sat_fat:.1f}g) · limit with heart condition ⚠️")

#         if omega3 > 0.5:
#             score += 6
#             reasons.append(f"Omega-3 ({omega3:.1f}g) · supports heart health")

#         if food.cholesterol_mg and food.cholesterol_mg > 200:
#             score -= 5
#             warnings.append("High cholesterol content · limit with CVD risk")

#         # Low HDL — encourage foods that raise good cholesterol
#         if conditions.get("low_hdl") and omega3 > 0.3:
#             score += 3
#             reasons.append("May help raise HDL (good cholesterol)")

#     # ── 8. ARTHRITIS / GOUT scoring ──────────────────────────────
#     if conditions.get("has_arthritis"):
#         purine = getattr(food, "purine_level", "Low") or "Low"
#         if purine.lower() == "low":
#             score += 5
#             reasons.append("Low purine · safe for joint health")
#         elif purine.lower() == "high":
#             score -= 8
#             warnings.append("High purine · avoid with gout / arthritis ⚠️")

#         crp_elevated = conditions.get("crp") and conditions["crp"] > 5
#         if crp_elevated and food.omega_3_g and food.omega_3_g > 0.3:
#             score += 4
#             reasons.append("Anti-inflammatory omega-3 · may help reduce CRP")

#     # ── 9. GASTRIC ISSUES scoring ────────────────────────────────
#     if conditions.get("has_gastric"):
#         fodmap = getattr(food, "fodmap_level", "Low") or "Low"
#         spice  = getattr(food, "spice_level",  "Low") or "Low"
#         if fodmap.lower() == "low":
#             score += 5
#             reasons.append("Low FODMAP · gentle on digestion")
#         elif fodmap.lower() == "high":
#             score -= 6
#             warnings.append("High FODMAP · may trigger IBS/GERD symptoms ⚠️")
#         if spice.lower() in ("high", "moderate"):
#             score -= 4
#             warnings.append("Spicy · may aggravate gastric issues")

#     # ── 10. THYROID scoring ──────────────────────────────────────
#     if conditions.get("has_thyroid"):
#         # Selenium and iodine support thyroid function
#         selenium = food.selenium_mcg or 0
#         iodine   = food.iodine_mcg   or 0
#         if selenium > 10:
#             score += 3
#             reasons.append(f"Selenium ({selenium:.0f}mcg) · supports thyroid function")
#         if iodine > 50:
#             score += 3
#             reasons.append(f"Iodine ({iodine:.0f}mcg) · supports thyroid function")

#     # ── 11. VITAMIN DEFICIENCY scoring ──────────────────────────
#     if conditions.get("low_vitamin_d") and food.vitamin_d_mcg and food.vitamin_d_mcg > 2:
#         score += 4
#         reasons.append(f"Vitamin D ({food.vitamin_d_mcg:.1f}mcg) · you may be deficient")

#     if conditions.get("low_vitamin_b12") and food.vitamin_b12_mcg and food.vitamin_b12_mcg > 0.5:
#         score += 4
#         reasons.append(f"Vitamin B12 ({food.vitamin_b12_mcg:.1f}mcg) · you may be deficient")

#     # ── 12. General fiber (3 pts) ────────────────────────────────
#     # Only add if not already counted under diabetes
#     if not conditions.get("is_diabetic") and food.fiber and food.fiber >= 3:
#         score += 3
#         reasons.append(f"Good fiber · {food.fiber:.1f}g")

#     # ── General warnings (always applied) ───────────────────────
#     if not conditions.get("is_hypertensive"):
#         if food.sodium_mg and food.sodium_mg > 600:
#             warnings.append("High sodium · watch intake")
#     if not conditions.get("is_diabetic"):
#         if food.estimated_gi and food.estimated_gi > 70:
#             warnings.append("High GI · may spike blood sugar")
#     if not conditions.get("has_heart"):
#         if food.saturated_fat_g and food.saturated_fat_g > 5:
#             warnings.append("High saturated fat")

#     if not reasons:
#         reasons.append("Nutritious choice for your goals")

#     return round(score, 2), reasons, warnings or None, fills_gap


# # ────────────────────────────────────────────────────────────────
# # SOURCE A — Food DB
# # ────────────────────────────────────────────────────────────────

# def _get_db_candidates(remaining, profile, meal_type=None, limit=30):
#     from userFood.models import FoodItem

#     rem_cal = remaining["calories"]
#     qs = FoodItem.objects.all()

#     # ── Diet type / veg filter ──
#     diet_type = getattr(profile, "diet_type", "") or ""
#     food_pref = getattr(profile, "food_preference", "") or ""
#     qs = qs.filter(_get_diet_type_q(diet_type or food_pref))

#     # ── Calorie ceiling ──
#     if rem_cal > 0:
#         qs = qs.filter(calories__lte=rem_cal * 0.85)

#     qs = qs.filter(protein__gt=0)

#     # ── Allergen exclusion ──
#     allergies_raw = getattr(profile, "allergies", "") or ""
#     for allergen in [a.strip() for a in allergies_raw.split(",") if a.strip()]:
#         qs = qs.exclude(allergens__name__icontains=allergen)

#     # ── Meal type filter ──
#     if meal_type:
#         qs = qs.filter(meal_types__name__icontains=meal_type)

#     return list(qs.prefetch_related("food_types", "meal_types", "allergens").distinct()[:limit])


# # ────────────────────────────────────────────────────────────────
# # SOURCE B — Nutritionist Diet Plan
# # ────────────────────────────────────────────────────────────────

# def _get_plan_candidates(user):
#     from diet.models import DietRecommendation
#     from userFood.models import UserMeal, FoodItem

#     today = timezone.now().date()
#     plan = (
#         DietRecommendation.objects
#         .filter(user=user, status="approved", is_deleted=False)
#         .order_by("-created_at").first()
#     )
#     if not plan or not plan.meals:
#         return [], None

#     try:
#         days_elapsed = (today - plan.for_week_starting).days
#     except Exception:
#         days_elapsed = 0

#     plan_keys = list(plan.meals.keys())
#     day_key = (
#         f"Day {days_elapsed + 1}"
#         if f"Day {days_elapsed + 1}" in plan.meals
#         else plan_keys[days_elapsed % len(plan_keys)]
#     )
#     day_meals = plan.meals.get(day_key, {})

#     logged_today = set(
#         UserMeal.objects.filter(user=user, date=today).values_list("food_name", flat=True)
#     )

#     candidates    = []
#     plan_reminder = None

#     if isinstance(day_meals, dict):
#         meal_items = day_meals.items()
#     elif isinstance(day_meals, list):
#         meal_items = [
#             (item.get("meal") or item.get("meal_name") or f"Meal {i+1}", item)
#             for i, item in enumerate(day_meals)
#             if isinstance(item, dict)
#         ]
#     else:
#         meal_items = []

#     for meal_name, meal_data in meal_items:
#         if meal_name in ("daily_totals", "daily_targets", "suggestion_flags"):
#             continue

#         food_name = None
#         if isinstance(meal_data, dict):
#             food_name = (
#                 meal_data.get("food_name")
#                 or meal_data.get("item")
#                 or meal_data.get("name")
#             )
#         elif isinstance(meal_data, list):
#             for item in meal_data:
#                 if isinstance(item, dict):
#                     food_name = (
#                         item.get("food_name")
#                         or item.get("item")
#                         or item.get("name")
#                     )
#                     break
#         elif isinstance(meal_data, str):
#             food_name = meal_data

#         if not food_name or food_name in logged_today:
#             continue

#         food_obj = FoodItem.objects.filter(name__iexact=food_name).first()
#         if food_obj:
#             candidates.append((food_obj, meal_name, day_key, True))
#         if plan_reminder is None:
#             plan_reminder = {
#                 "message": f"Your plan has {food_name} for {meal_name} — you haven't logged it yet",
#                 "day":     day_key,
#                 "meal":    meal_name,
#                 "food":    food_name,
#             }

#     return candidates, plan_reminder


# # ────────────────────────────────────────────────────────────────
# # SOURCE C — Gemini Fallback
# # ────────────────────────────────────────────────────────────────

# def _get_gemini_candidates(remaining, profile, meal_type=None):
#     try:
#         from utils.gemini import suggest_foods_gemini
#         return suggest_foods_gemini(remaining, profile, meal_type)
#     except Exception as exc:
#         logger.warning(f"Gemini suggestion fallback failed: {exc}")
#         return []


# # ────────────────────────────────────────────────────────────────
# # MAIN PUBLIC FUNCTION
# # ────────────────────────────────────────────────────────────────

# def build_suggestions(user, meal_type=None, limit=5) -> dict:
#     from userProfile.models import UserProfile

#     try:
#         profile = UserProfile.objects.get(user=user)
#     except UserProfile.DoesNotExist:
#         return {"error": "Profile not found. Please complete your profile first."}

#     nutrient_data = get_remaining_nutrients(user)
#     if not nutrient_data:
#         return {"error": "Could not calculate targets. Please complete your profile."}

#     remaining = nutrient_data["remaining"]
#     goal      = nutrient_data["goal"]

#     if remaining["calories"] < 50:
#         return {
#             "message":             "🎉 You've hit your calorie goal for today!",
#             "remaining_nutrients": remaining,
#             "consumed":            nutrient_data["consumed"],
#             "targets":             nutrient_data["targets"],
#             "goal":                goal,
#             "suggestions":         [],
#             "plan_reminder":       None,
#         }

#     country          = getattr(profile, "country", "") or ""
#     country_keywords = _get_country_keywords(country)

#     # ── Load lab data and derive conditions ──────────────────────
#     lab_data   = _get_latest_lab_data(user)
#     conditions = _derive_conditions_from_labs(lab_data, profile)

#     # Build pool
#     db_foods                       = _get_db_candidates(remaining, profile, meal_type)
#     plan_candidates, plan_reminder = _get_plan_candidates(user)

#     seen_ids   = set()
#     candidates = []

#     for food_obj, meal_name, day_key, _ in plan_candidates:
#         if food_obj.id not in seen_ids:
#             candidates.append((food_obj, True, meal_name, day_key))
#             seen_ids.add(food_obj.id)

#     for food_obj in db_foods:
#         if food_obj.id not in seen_ids:
#             candidates.append((food_obj, False, None, None))
#             seen_ids.add(food_obj.id)

#     if len(candidates) < 5:
#         for food_obj in _get_gemini_candidates(remaining, profile, meal_type):
#             if food_obj.id not in seen_ids:
#                 candidates.append((food_obj, False, None, None))
#                 seen_ids.add(food_obj.id)

#     # Score & rank
#     scored = []
#     for food_obj, from_plan, meal_name, day_key in candidates:
#         score, reasons, warnings, fills_gap = _score_food(
#             food=food_obj,
#             remaining=remaining,
#             goal=goal,
#             country_keywords=country_keywords,
#             conditions=conditions,
#             from_plan=from_plan,
#         )
#         scored.append({
#             "food_id":    food_obj.id,
#             "food_name":  food_obj.name,
#             "calories":   food_obj.calories  or 0,
#             "protein":    food_obj.protein   or 0,
#             "carbs":      food_obj.carbs     or 0,
#             "fats":       food_obj.fats      or 0,
#             "fiber":      food_obj.fiber     or 0,
#             "sugar":      food_obj.sugar     or 0,
#             "meal_type":  meal_name or (
#                 food_obj.meal_types.first().name if food_obj.meal_types.exists() else None
#             ),
#             "source":     "diet_plan" if from_plan else "db",
#             "score":      score,
#             "reasons":    reasons,
#             "warnings":   warnings,
#             "fills_gap":  fills_gap,
#         })

#     scored.sort(key=lambda x: x["score"], reverse=True)

#     targets = nutrient_data["targets"]
#     ws_push = (
#         remaining["protein_g"] > targets["protein_g"] * 0.30
#         or nutrient_data["pct_cal_consumed"] < 60
#     )
#     hour    = timezone.localtime(timezone.now()).hour
#     email_q = (19 <= hour < 20)

#     # Build active conditions list for API response transparency
#     active_conditions = [k for k, v in conditions.items()
#                          if isinstance(v, bool) and v and k.startswith(("is_", "has_", "low_"))]

#     return {
#         "remaining_nutrients": remaining,
#         "consumed":            nutrient_data["consumed"],
#         "targets":             targets,
#         "goal":                goal,
#         "suggestions":         scored[:limit],
#         "plan_reminder":       plan_reminder,
#         "health_context": {
#             "active_conditions": active_conditions,
#             "lab_data_used":     bool(lab_data),
#         },
#         "delivery": {
#             "ws_should_push":     ws_push,
#             "email_should_queue": email_q,
#         },
#         "_meta": {"country": country, "pool_size": len(candidates)},
#     }

# userFood/suggestions.py
# ================================================================
# Smart Food Suggestion Engine
# Sources: Food DB  +  Nutritionist Diet Plan  +  Gemini Fallback
# ================================================================

import logging
from django.utils import timezone
from django.db.models import Sum, Q

logger = logging.getLogger(__name__)

# ── Country → cuisine keyword map ────────────────────────────────
COUNTRY_CUISINE_MAP = {
    "india":      ["paneer", "dal", "roti", "sabzi", "rice", "idli", "dosa",
                   "paratha", "khichdi", "sambar", "curry", "chapati", "raita",
                   "poha", "upma", "uttapam", "biryani", "pulao", "chole",
                   "rajma", "kadhi", "halwa", "lassi"],
    "usa":        ["oatmeal", "sandwich", "salad", "wrap", "quinoa", "smoothie",
                   "granola", "eggs", "avocado", "bagel", "turkey", "chicken breast"],
    "uk":         ["porridge", "beans", "toast", "salad", "soup", "sandwich"],
    "pakistan":   ["roti", "dal", "curry", "biryani", "nihari", "haleem", "paratha"],
    "bangladesh": ["rice", "dal", "fish", "curry", "hilsa", "bhaji"],
    "sri lanka":  ["rice", "curry", "hoppers", "kottu", "sambal", "dhal"],
    "nepal":      ["dal bhat", "momo", "thukpa", "tarkari"],
    "china":      ["tofu", "noodles", "fried rice", "dumpling", "congee"],
    "japan":      ["tofu", "miso", "edamame", "rice", "soba", "salmon"],
    "italy":      ["pasta", "salad", "soup", "risotto", "bruschetta"],
    "mexico":     ["beans", "tortilla", "avocado", "quinoa", "salsa"],
    "thailand":   ["rice", "tofu", "papaya", "curry", "noodles"],
}

GOAL_STRATEGY = {
    "lose weight":     {"calorie_factor": 0.50, "protein_priority": True},
    "maintain weight": {"calorie_factor": 0.60, "protein_priority": False},
    "gain weight":     {"calorie_factor": 0.70, "protein_priority": True},
}


# ────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────

def _get_country_keywords(country: str) -> list:
    return COUNTRY_CUISINE_MAP.get(country.lower().strip(), []) if country else []


def _food_matches_country(food_name: str, keywords: list) -> bool:
    if not keywords:
        return True
    return any(kw in food_name.lower() for kw in keywords)


def _get_diet_type_q(diet_type: str) -> Q:
    dt = (diet_type or "").lower().strip()
    if dt in ("vegetarian", "vegan", "eggetarian"):
        return ~Q(food_types__name__icontains="Non-Vegetarian")
    return Q()


# ────────────────────────────────────────────────────────────────
# LAB REPORT READER
# ────────────────────────────────────────────────────────────────

def _get_latest_lab_data(user) -> dict:
    """
    Reads the most recent LabReport for the user.
    Returns a flat dict of clinically relevant values.
    All values are None if no report exists.
    """
    try:
        from userProfile.models import LabReport
        report = LabReport.objects.filter(user=user).order_by("-report_date").first()
        if not report:
            return {}
        return {
            "hba1c":                   report.hba1c,
            "fasting_blood_sugar":     report.fasting_blood_sugar,
            "postprandial_sugar":      report.postprandial_sugar,
            "ldl_cholesterol":         report.ldl_cholesterol,
            "hdl_cholesterol":         report.hdl_cholesterol,
            "triglycerides":           report.triglycerides,
            "blood_pressure_systolic": report.blood_pressure_systolic,
            "uric_acid":               report.uric_acid,
            "crp":                     report.crp,
            "vitamin_d3":              report.vitamin_d3,
            "vitamin_b12":             report.vitamin_b12,
            "tsh":                     report.tsh,
            "creatinine":              report.creatinine,
        }
    except Exception as exc:
        logger.warning(f"Lab report fetch failed: {exc}")
        return {}


def _derive_conditions_from_labs(lab: dict, profile) -> dict:
    """
    Derives or confirms medical conditions from lab values.
    Lab data overrides/supplements profile boolean flags.
    Returns a conditions dict used throughout scoring.
    """
    # Start from profile boolean flags
    is_diabetic     = bool(getattr(profile, "is_diabetic",        False))
    is_hypertensive = bool(getattr(profile, "is_hypertensive",    False))
    has_heart       = bool(getattr(profile, "has_heart_condition", False))
    has_arthritis   = bool(getattr(profile, "has_arthritis",       False))
    has_gastric     = bool(getattr(profile, "has_gastric_issues",  False))
    has_thyroid     = bool(getattr(profile, "has_thyroid_disorder",False))

    # Upgrade flags from lab values if available
    if lab.get("hba1c") and lab["hba1c"] >= 6.5:
        is_diabetic = True          # HbA1c ≥ 6.5% → confirmed diabetes
    elif lab.get("fasting_blood_sugar") and lab["fasting_blood_sugar"] >= 126:
        is_diabetic = True          # FBS ≥ 126 mg/dL → diabetes

    if lab.get("blood_pressure_systolic") and lab["blood_pressure_systolic"] >= 140:
        is_hypertensive = True      # Systolic ≥ 140 mmHg → hypertension

    if lab.get("ldl_cholesterol") and lab["ldl_cholesterol"] >= 160:
        has_heart = True            # High LDL → elevated cardiovascular risk
    if lab.get("triglycerides") and lab["triglycerides"] >= 200:
        has_heart = True            # High TGs → elevated cardiovascular risk

    if lab.get("uric_acid") and lab["uric_acid"] >= 7.0:
        has_arthritis = True        # High uric acid → gout risk

    # Blood sugar control level (for granular diabetic scoring)
    sugar_controlled = True
    if lab.get("hba1c"):
        sugar_controlled = lab["hba1c"] < 7.0
    elif lab.get("fasting_blood_sugar"):
        sugar_controlled = lab["fasting_blood_sugar"] < 130

    # Vitamin deficiencies
    low_vitamin_d  = lab.get("vitamin_d3")  is not None and lab["vitamin_d3"]  < 20
    low_vitamin_b12= lab.get("vitamin_b12") is not None and lab["vitamin_b12"] < 200
    low_hdl        = lab.get("hdl_cholesterol") is not None and lab["hdl_cholesterol"] < 40

    return {
        "is_diabetic":       is_diabetic,
        "is_hypertensive":   is_hypertensive,
        "has_heart":         has_heart,
        "has_arthritis":     has_arthritis,
        "has_gastric":       has_gastric,
        "has_thyroid":       has_thyroid,
        "sugar_controlled":  sugar_controlled,
        "low_vitamin_d":     low_vitamin_d,
        "low_vitamin_b12":   low_vitamin_b12,
        "low_hdl":           low_hdl,
        # Raw lab values for scoring
        "hba1c":             lab.get("hba1c"),
        "fasting_sugar":     lab.get("fasting_blood_sugar"),
        "ldl":               lab.get("ldl_cholesterol"),
        "triglycerides":     lab.get("triglycerides"),
        "uric_acid":         lab.get("uric_acid"),
    }


# ────────────────────────────────────────────────────────────────
# NUTRIENT CALCULATIONS
# ────────────────────────────────────────────────────────────────

def get_today_consumed(user) -> dict:
    from userFood.models import UserMeal
    today = timezone.now().date()
    agg = UserMeal.objects.filter(user=user, date=today).aggregate(
        calories=Sum("calories"),
        protein=Sum("protein"),
        carbs=Sum("carbs"),
        fats=Sum("fats"),
        sugar=Sum("sugar"),
        fiber=Sum("fiber"),
    )
    return {k: round(v or 0, 2) for k, v in agg.items()}


def _get_period_days(period: str | None) -> int:
    """
    Resolves the averaging period in days.
    Priority: explicit param → Django setting → default (1 = daily)

    period values:
      "daily"   → 1 day  (today only)
      "weekly"  → 7 days (7-day rolling average)
      None      → reads settings.SUGGESTION_PERIOD_DAYS (default 1)
    """
    from django.conf import settings

    if period == "weekly":
        return 7
    if period == "daily":
        return 1
    # Fall back to global setting
    return int(getattr(settings, "SUGGESTION_PERIOD_DAYS", 1))


def get_remaining_nutrients(user, period: str | None = None) -> dict:
    """
    Uses the same get_target_nutrients() as the dashboard
    so calorie targets are always consistent.

    period:
      "daily"  → compare today's intake vs daily target  (default)
      "weekly" → compare 7-day average intake vs daily target
                 (smooths out one-off binge/fast days — useful for HbA1c tracking)
    """
    from utils.utils import get_target_nutrients
    from userFood.models import UserMeal

    today        = timezone.now().date()
    period_days  = _get_period_days(period)
    targets      = get_target_nutrients(user)

    cal_target     = targets.get("recommended_calories", 2000)
    protein_target = targets.get("macronutrients", {}).get("protein_g", 50)
    carbs_target   = targets.get("macronutrients", {}).get("carbs_g", 250)
    fats_target    = targets.get("macronutrients", {}).get("fats_g", 65)
    sugar_target   = targets.get("macronutrients", {}).get("sugar_g", 28)
    fiber_target   = targets.get("macronutrients", {}).get("fiber_g", 25)

    if period_days == 1:
        # ── Daily mode: just today ───────────────────────────────
        meals = UserMeal.objects.filter(user=user, date=today)
        agg = meals.aggregate(
            calories=Sum("calories"), protein=Sum("protein"),
            carbs=Sum("carbs"),       fats=Sum("fats"),
            sugar=Sum("sugar"),       fiber=Sum("fiber"),
        )
        consumed = {k: float(v or 0) for k, v in agg.items()}
        period_label = "daily"
    else:
        # ── Weekly mode: rolling N-day average ──────────────────
        # Compare average daily intake over the past N days vs target.
        # This mirrors the HbA1c concept: sustained average matters more
        # than a single day's reading.
        from datetime import timedelta
        start_date = today - timedelta(days=period_days - 1)
        meals = UserMeal.objects.filter(user=user, date__range=(start_date, today))
        agg = meals.aggregate(
            calories=Sum("calories"), protein=Sum("protein"),
            carbs=Sum("carbs"),       fats=Sum("fats"),
            sugar=Sum("sugar"),       fiber=Sum("fiber"),
        )
        # Divide total by number of days to get daily average
        consumed = {k: round(float(v or 0) / period_days, 2) for k, v in agg.items()}
        period_label = f"{period_days}-day average"

    pct = round((consumed["calories"] / cal_target * 100), 1) if cal_target else 0

    return {
        "remaining": {
            "calories":  max(0, round(cal_target     - consumed["calories"], 1)),
            "protein_g": max(0, round(protein_target - consumed["protein"],  2)),
            "carbs_g":   max(0, round(carbs_target   - consumed["carbs"],    2)),
            "fats_g":    max(0, round(fats_target    - consumed["fats"],     2)),
            "sugar_g":   max(0, round(sugar_target   - consumed["sugar"],    2)),
            "fiber_g":   max(0, round(fiber_target   - consumed["fiber"],    2)),
        },
        "consumed": consumed,
        "targets": {
            "calories":  cal_target,
            "protein_g": protein_target,
            "carbs_g":   carbs_target,
            "fats_g":    fats_target,
            "sugar_g":   sugar_target,
            "fiber_g":   fiber_target,
        },
        "goal":             targets.get("weight_target", {}).get("goal", "Maintain Weight"),
        "pct_cal_consumed": pct,
        "period":           period_label,
    }


# ────────────────────────────────────────────────────────────────
# SCORING  (medical history fully integrated)
# ────────────────────────────────────────────────────────────────

def _score_food(food, remaining, goal, country_keywords, conditions, from_plan=False):
    """
    Scores a food item against the user's remaining macros and medical profile.

    conditions dict (from _derive_conditions_from_labs):
      is_diabetic, is_hypertensive, has_heart, has_arthritis,
      has_gastric, has_thyroid, sugar_controlled, low_vitamin_d,
      low_vitamin_b12, low_hdl, hba1c, fasting_sugar, ldl, triglycerides, uric_acid
    """
    score = 0; reasons = []; warnings = []; fills_gap = {}

    rem_cal  = remaining["calories"]
    rem_prot = remaining["protein_g"]
    rem_sugar= remaining["sugar_g"]
    rem_fiber= remaining["fiber_g"]
    strategy = GOAL_STRATEGY.get(goal.lower(), GOAL_STRATEGY["maintain weight"])

    # ── 1. Calorie fit (30 pts) ───────────────────────────────────
    ideal_cal = rem_cal * strategy["calorie_factor"]
    if ideal_cal > 0 and food.calories and food.calories > 0:
        diff  = abs(food.calories - ideal_cal) / ideal_cal
        score += max(0, 30 * (1 - diff))
        if diff < 0.25:
            reasons.append(
                f"Right portion · {food.calories:.0f} kcal fits your remaining {rem_cal:.0f} kcal"
            )
            fills_gap["calories"] = f"{food.calories:.0f} of {rem_cal:.0f} kcal remaining"

    # ── 2. Protein gap fill (40 pts) ─────────────────────────────
    if rem_prot > 0 and food.protein and food.protein > 0:
        ratio = food.protein / rem_prot
        score += min(40, ratio * 40)
        pct   = round(ratio * 100, 1)
        if pct >= 10:
            reasons.append(f"High protein · fills {pct}% of your {rem_prot:.0f}g gap")
            fills_gap["protein"] = f"{food.protein:.1f}g of {rem_prot:.0f}g remaining"

    # ── 3. Diet plan bonus (20 pts) ──────────────────────────────
    if from_plan:
        score += 20
        reasons.append("Matches your nutritionist plan")

    # ── 4. Regional cuisine (10 pts) ─────────────────────────────
    if country_keywords and _food_matches_country(food.name, country_keywords):
        score += 10
        reasons.append("Suits your regional cuisine")

    # ── 5. DIABETES scoring ──────────────────────────────────────
    if conditions.get("is_diabetic"):
        gi = food.estimated_gi
        sugar = food.sugar or 0

        if gi:
            if gi < 40:
                score += 10
                reasons.append(f"Very low GI ({gi:.0f}) · excellent for blood sugar control")
            elif gi < 55:
                score += 6
                reasons.append(f"Low GI ({gi:.0f}) · good for blood sugar")
            elif gi >= 70:
                score -= 10
                warnings.append("High GI · may spike blood sugar ⚠️")

        if sugar < 5:
            score += 5
            reasons.append(f"Low sugar · {sugar:.1f}g per serving")
        elif sugar > 15:
            score -= 8
            warnings.append(f"High sugar ({sugar:.1f}g) · avoid if blood sugar is uncontrolled")

        # Fiber helps blood sugar — extra weight for diabetics
        if food.fiber and food.fiber >= 5:
            score += 5
            reasons.append(f"High fiber ({food.fiber:.1f}g) · slows sugar absorption")

        # If poorly controlled diabetes, be stricter
        if not conditions.get("sugar_controlled"):
            if gi and gi >= 55:
                score -= 5
            if sugar > 10:
                score -= 5

    # ── 6. HYPERTENSION scoring ──────────────────────────────────
    if conditions.get("is_hypertensive"):
        sodium = food.sodium_mg or 0
        potassium = food.potassium_mg or 0

        if sodium < 140:
            score += 8
            reasons.append(f"Very low sodium ({sodium:.0f}mg) · excellent for blood pressure")
        elif sodium < 300:
            score += 4
            reasons.append("Low sodium · heart-friendly")
        elif sodium > 600:
            score -= 10
            warnings.append(f"High sodium ({sodium:.0f}mg) · avoid with hypertension ⚠️")

        if potassium > 400:
            score += 4
            reasons.append(f"High potassium ({potassium:.0f}mg) · helps lower blood pressure")

    # ── 7. HEART CONDITION scoring ───────────────────────────────
    if conditions.get("has_heart"):
        sat_fat = food.saturated_fat_g or 0
        omega3  = food.omega_3_g or 0

        if sat_fat < 2:
            score += 6
            reasons.append("Low saturated fat · heart-safe")
        elif sat_fat > 5:
            score -= 8
            warnings.append(f"High saturated fat ({sat_fat:.1f}g) · limit with heart condition ⚠️")

        if omega3 > 0.5:
            score += 6
            reasons.append(f"Omega-3 ({omega3:.1f}g) · supports heart health")

        if food.cholesterol_mg and food.cholesterol_mg > 200:
            score -= 5
            warnings.append("High cholesterol content · limit with CVD risk")

        # Low HDL — encourage foods that raise good cholesterol
        if conditions.get("low_hdl") and omega3 > 0.3:
            score += 3
            reasons.append("May help raise HDL (good cholesterol)")

    # ── 8. ARTHRITIS / GOUT scoring ──────────────────────────────
    if conditions.get("has_arthritis"):
        purine = getattr(food, "purine_level", "Low") or "Low"
        if purine.lower() == "low":
            score += 5
            reasons.append("Low purine · safe for joint health")
        elif purine.lower() == "high":
            score -= 8
            warnings.append("High purine · avoid with gout / arthritis ⚠️")

        crp_elevated = conditions.get("crp") and conditions["crp"] > 5
        if crp_elevated and food.omega_3_g and food.omega_3_g > 0.3:
            score += 4
            reasons.append("Anti-inflammatory omega-3 · may help reduce CRP")

    # ── 9. GASTRIC ISSUES scoring ────────────────────────────────
    if conditions.get("has_gastric"):
        fodmap = getattr(food, "fodmap_level", "Low") or "Low"
        spice  = getattr(food, "spice_level",  "Low") or "Low"
        if fodmap.lower() == "low":
            score += 5
            reasons.append("Low FODMAP · gentle on digestion")
        elif fodmap.lower() == "high":
            score -= 6
            warnings.append("High FODMAP · may trigger IBS/GERD symptoms ⚠️")
        if spice.lower() in ("high", "moderate"):
            score -= 4
            warnings.append("Spicy · may aggravate gastric issues")

    # ── 10. THYROID scoring ──────────────────────────────────────
    if conditions.get("has_thyroid"):
        # Selenium and iodine support thyroid function
        selenium = food.selenium_mcg or 0
        iodine   = food.iodine_mcg   or 0
        if selenium > 10:
            score += 3
            reasons.append(f"Selenium ({selenium:.0f}mcg) · supports thyroid function")
        if iodine > 50:
            score += 3
            reasons.append(f"Iodine ({iodine:.0f}mcg) · supports thyroid function")

    # ── 11. VITAMIN DEFICIENCY scoring ──────────────────────────
    if conditions.get("low_vitamin_d") and food.vitamin_d_mcg and food.vitamin_d_mcg > 2:
        score += 4
        reasons.append(f"Vitamin D ({food.vitamin_d_mcg:.1f}mcg) · you may be deficient")

    if conditions.get("low_vitamin_b12") and food.vitamin_b12_mcg and food.vitamin_b12_mcg > 0.5:
        score += 4
        reasons.append(f"Vitamin B12 ({food.vitamin_b12_mcg:.1f}mcg) · you may be deficient")

    # ── 12. General fiber (3 pts) ────────────────────────────────
    # Only add if not already counted under diabetes
    if not conditions.get("is_diabetic") and food.fiber and food.fiber >= 3:
        score += 3
        reasons.append(f"Good fiber · {food.fiber:.1f}g")

    # ── General warnings (always applied) ───────────────────────
    if not conditions.get("is_hypertensive"):
        if food.sodium_mg and food.sodium_mg > 600:
            warnings.append("High sodium · watch intake")
    if not conditions.get("is_diabetic"):
        if food.estimated_gi and food.estimated_gi > 70:
            warnings.append("High GI · may spike blood sugar")
    if not conditions.get("has_heart"):
        if food.saturated_fat_g and food.saturated_fat_g > 5:
            warnings.append("High saturated fat")

    if not reasons:
        reasons.append("Nutritious choice for your goals")

    return round(score, 2), reasons, warnings or None, fills_gap


# ────────────────────────────────────────────────────────────────
# SOURCE A — Food DB
# ────────────────────────────────────────────────────────────────

def _get_db_candidates(remaining, profile, meal_type=None, limit=30):
    from userFood.models import FoodItem

    rem_cal = remaining["calories"]
    qs = FoodItem.objects.all()

    # ── Diet type / veg filter ──
    diet_type = getattr(profile, "diet_type", "") or ""
    food_pref = getattr(profile, "food_preference", "") or ""
    qs = qs.filter(_get_diet_type_q(diet_type or food_pref))

    # ── Calorie ceiling ──
    if rem_cal > 0:
        qs = qs.filter(calories__lte=rem_cal * 0.85)

    qs = qs.filter(protein__gt=0)

    # ── Allergen exclusion ──
    allergies_raw = getattr(profile, "allergies", "") or ""
    for allergen in [a.strip() for a in allergies_raw.split(",") if a.strip()]:
        qs = qs.exclude(allergens__name__icontains=allergen)

    # ── Meal type filter ──
    if meal_type:
        qs = qs.filter(meal_types__name__icontains=meal_type)

    return list(qs.prefetch_related("food_types", "meal_types", "allergens").distinct()[:limit])


# ────────────────────────────────────────────────────────────────
# SOURCE B — Nutritionist Diet Plan
# ────────────────────────────────────────────────────────────────

def _get_plan_candidates(user):
    from diet.models import DietRecommendation
    from userFood.models import UserMeal, FoodItem

    today = timezone.now().date()
    plan = (
        DietRecommendation.objects
        .filter(user=user, status="approved", is_deleted=False)
        .order_by("-created_at").first()
    )
    if not plan or not plan.meals:
        return [], None

    try:
        days_elapsed = (today - plan.for_week_starting).days
    except Exception:
        days_elapsed = 0

    plan_keys = list(plan.meals.keys())
    day_key = (
        f"Day {days_elapsed + 1}"
        if f"Day {days_elapsed + 1}" in plan.meals
        else plan_keys[days_elapsed % len(plan_keys)]
    )
    day_meals = plan.meals.get(day_key, {})

    logged_today = set(
        UserMeal.objects.filter(user=user, date=today).values_list("food_name", flat=True)
    )

    candidates    = []
    plan_reminder = None

    if isinstance(day_meals, dict):
        meal_items = day_meals.items()
    elif isinstance(day_meals, list):
        meal_items = [
            (item.get("meal") or item.get("meal_name") or f"Meal {i+1}", item)
            for i, item in enumerate(day_meals)
            if isinstance(item, dict)
        ]
    else:
        meal_items = []

    for meal_name, meal_data in meal_items:
        if meal_name in ("daily_totals", "daily_targets", "suggestion_flags"):
            continue

        food_name = None
        if isinstance(meal_data, dict):
            food_name = (
                meal_data.get("food_name")
                or meal_data.get("item")
                or meal_data.get("name")
            )
        elif isinstance(meal_data, list):
            for item in meal_data:
                if isinstance(item, dict):
                    food_name = (
                        item.get("food_name")
                        or item.get("item")
                        or item.get("name")
                    )
                    break
        elif isinstance(meal_data, str):
            food_name = meal_data

        if not food_name or food_name in logged_today:
            continue

        food_obj = FoodItem.objects.filter(name__iexact=food_name).first()
        if food_obj:
            candidates.append((food_obj, meal_name, day_key, True))
        if plan_reminder is None:
            plan_reminder = {
                "message": f"Your plan has {food_name} for {meal_name} — you haven't logged it yet",
                "day":     day_key,
                "meal":    meal_name,
                "food":    food_name,
            }

    return candidates, plan_reminder


# ────────────────────────────────────────────────────────────────
# SOURCE C — Gemini Fallback
# ────────────────────────────────────────────────────────────────

def _get_gemini_candidates(remaining, profile, meal_type=None):
    try:
        from utils.gemini import suggest_foods_gemini
        return suggest_foods_gemini(remaining, profile, meal_type)
    except Exception as exc:
        logger.warning(f"Gemini suggestion fallback failed: {exc}")
        return []


# ────────────────────────────────────────────────────────────────
# MAIN PUBLIC FUNCTION
# ────────────────────────────────────────────────────────────────

def build_suggestions(user, meal_type=None, limit=5, period=None) -> dict:
    from userProfile.models import UserProfile

    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return {"error": "Profile not found. Please complete your profile first."}

    nutrient_data = get_remaining_nutrients(user, period=period)
    if not nutrient_data:
        return {"error": "Could not calculate targets. Please complete your profile."}

    remaining = nutrient_data["remaining"]
    goal      = nutrient_data["goal"]

    if remaining["calories"] < 50:
        return {
            "message":             "🎉 You've hit your calorie goal for today!",
            "remaining_nutrients": remaining,
            "consumed":            nutrient_data["consumed"],
            "targets":             nutrient_data["targets"],
            "goal":                goal,
            "suggestions":         [],
            "plan_reminder":       None,
        }

    country          = getattr(profile, "country", "") or ""
    country_keywords = _get_country_keywords(country)

    # ── Load lab data and derive conditions ──────────────────────
    lab_data   = _get_latest_lab_data(user)
    conditions = _derive_conditions_from_labs(lab_data, profile)

    # Build pool
    db_foods                       = _get_db_candidates(remaining, profile, meal_type)
    plan_candidates, plan_reminder = _get_plan_candidates(user)

    seen_ids   = set()
    candidates = []

    for food_obj, meal_name, day_key, _ in plan_candidates:
        if food_obj.id not in seen_ids:
            candidates.append((food_obj, True, meal_name, day_key))
            seen_ids.add(food_obj.id)

    for food_obj in db_foods:
        if food_obj.id not in seen_ids:
            candidates.append((food_obj, False, None, None))
            seen_ids.add(food_obj.id)

    if len(candidates) < 5:
        for food_obj in _get_gemini_candidates(remaining, profile, meal_type):
            if food_obj.id not in seen_ids:
                candidates.append((food_obj, False, None, None))
                seen_ids.add(food_obj.id)

    # Score & rank
    scored = []
    for food_obj, from_plan, meal_name, day_key in candidates:
        score, reasons, warnings, fills_gap = _score_food(
            food=food_obj,
            remaining=remaining,
            goal=goal,
            country_keywords=country_keywords,
            conditions=conditions,
            from_plan=from_plan,
        )
        scored.append({
            "food_id":    food_obj.id,
            "food_name":  food_obj.name,
            "calories":   food_obj.calories  or 0,
            "protein":    food_obj.protein   or 0,
            "carbs":      food_obj.carbs     or 0,
            "fats":       food_obj.fats      or 0,
            "fiber":      food_obj.fiber     or 0,
            "sugar":      food_obj.sugar     or 0,
            "meal_type":  meal_name or (
                food_obj.meal_types.first().name if food_obj.meal_types.exists() else None
            ),
            "source":     "diet_plan" if from_plan else "db",
            "score":      score,
            "reasons":    reasons,
            "warnings":   warnings,
            "fills_gap":  fills_gap,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    targets = nutrient_data["targets"]
    ws_push = (
        remaining["protein_g"] > targets["protein_g"] * 0.30
        or nutrient_data["pct_cal_consumed"] < 60
    )
    hour    = timezone.localtime(timezone.now()).hour
    email_q = (19 <= hour < 20)

    # Build active conditions list for API response transparency
    active_conditions = [k for k, v in conditions.items()
                         if isinstance(v, bool) and v and k.startswith(("is_", "has_", "low_"))]

    return {
        "remaining_nutrients": remaining,
        "consumed":            nutrient_data["consumed"],
        "targets":             targets,
        "goal":                goal,
        "suggestions":         scored[:limit],
        "plan_reminder":       plan_reminder,
        "health_context": {
            "active_conditions": active_conditions,
            "lab_data_used":     bool(lab_data),
        },
        "period":   nutrient_data.get("period", "daily"),
        "delivery": {
            "ws_should_push":     ws_push,
            "email_should_queue": email_q,
        },
        "_meta": {"country": country, "pool_size": len(candidates)},
    }