import dotenv
from userFood.models import FoodItem, FoodType, MealType, Allergen, LEVEL_CHOICES
from google import genai
from django.db import transaction
import json
import traceback
import time
import logging
import os
from pathlib import Path
from userFood.services.attribute_matcher import link_food_attributes

# === Changes made by Ananya (Start) ===
from userFood.gemini_attributes import apply_gemini_attributes_to_food_if_missing
# === Changes made by Ananya (End) ===


class GeminiUnavailableError(Exception):
    """Raised when Gemini returns a transient error (503, 429, network timeout)."""
    pass


# Load .env BEFORE anything else
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    dotenv.load_dotenv(env_path, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(f"❌ GEMINI_API_KEY not found in environment variables.")
client = genai.Client(api_key=GEMINI_API_KEY)
logger = logging.getLogger(__name__)

# Import Django models AFTER env is loaded


client = genai.Client(api_key=GEMINI_API_KEY)


def get_nullable_float(data: dict, key: str):
    """
    Safely extracts a float value from a dictionary.
    Returns None if the key is missing, the value is null, or it cannot be converted to a float.
    """
    value = data.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@transaction.atomic
def fetch_nutrition_from_gemini(food_name: str, quantity: float, unit: str) -> FoodItem:
    food_query = f"{quantity} {unit} of {food_name}"

    prompt = f"""
Return nutrition data for: "{food_query}"


Rules:
- Match the exact serving size specified.
- Use reliable nutrition data (USDA-style).
- Every numeric field MUST be a JSON number (e.g. 320.5), never a string, never null, never a placeholder.
- Output valid JSON only, no extra text.
# === Changes made by Ananya (Start) ===
You MUST preserve ALL existing response fields exactly as before.

Backwards compatible extension:
- Add a REQUIRED top-level field named "attributes".
- The "attributes" field must always be present.
- Generate at least 3 meaningful attributes whenever possible.
- Return an empty array only if no meaningful attributes exist.
- "attributes" must be an array of objects of the form:
  {{
    "name": <string>,
    "required": <boolean>,
    "options": [
      {{"value": <string>, "nutrition_multiplier": <number>}},
      ...
    ]
  }}
- If no meaningful attributes exist, return:
  "attributes": []
- Never omit the "attributes" field.
- Attributes inference must be dynamic (no hardcoding food-specific templates).
- Infer attributes that can affect serving size, ingredients, preparation, or nutrition.

{{
  "source_url": "",
  "food_item": {{
    "name": "Quesadilla",
    "default_quantity": {quantity},
    "default_unit": "{unit}",
    "gram_equivalent": 200,
    "calories": 450,
    "protein": 18.5,
    "carbs": 42.0,
    "fats": 22.0,
    "sugar": 2.1,
    "fiber": 3.0,
    "saturated_fat_g": 9.0,
    "trans_fat_g": 0.1,
    "estimated_gi": 55,
    "glycemic_load": 23,
    "sodium_mg": 680,
    "potassium_mg": 290,
    "iron_mg": 2.1,
    "calcium_mg": 310,
    "iodine_mcg": 0,
    "zinc_mg": 1.8,
    "magnesium_mcg": 28,
    "selenium_mcg": 12,
    "cholesterol_mg": 55,
    "omega_3_g": 0.1,
    "vitamin_d_mcg": 0.3,
    "vitamin_b12_mcg": 0.6,
    "fodmap_level": "Medium",
    "spice_level": "Low",
    "purine_level": "Low"
  }},
  "food_types": ["Non-Vegetarian"],
  "meal_types": ["Lunch", "Dinner"],
  "allergens": ["Gluten", "Dairy"],

  "attributes": [
    {{
      "name": "Size",
      "required": true,
      "options": [
        {{"value": "Small", "nutrition_multiplier": 0.8}},
        {{"value": "Medium", "nutrition_multiplier": 1.0}},
        {{"value": "Large", "nutrition_multiplier": 1.3}}
      ]
    }}
  ]
}}

Now return the same JSON structure with correct values for: "{food_query}"
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"temperature": 0.0,
                    "response_mime_type": "application/json"},
        )
        print("\n========== GEMINI RESPONSE ==========")
        print(response.text)
        print("====================================\n")

        data = json.loads(response.text)
        item_data = data.get("food_item")
        if not item_data:
            raise ValueError("Gemini response missing 'food_item'.")

        standardized_name = (item_data.get('name') or food_name).strip()

        def require_float(d, key, fallback=0.0):
            """Parse a numeric value; return fallback only if truly absent or unparseable."""
            val = d.get(key)
            if val is None:
                return fallback
            try:
                return float(val)
            except (ValueError, TypeError):
                return fallback

        food_item_defaults = {
            'default_quantity': require_float(item_data, 'default_quantity', quantity),
            'default_unit':     item_data.get('default_unit') or unit,
            'gram_equivalent':  require_float(item_data, 'gram_equivalent', 0.0),
            'source_url':       data.get('source_url') or '',
            'calories':         require_float(item_data, 'calories'),
            'protein':          require_float(item_data, 'protein'),
            'carbs':            require_float(item_data, 'carbs'),
            'fats':             require_float(item_data, 'fats'),
            'sugar':            require_float(item_data, 'sugar'),
            'fiber':            require_float(item_data, 'fiber'),
            'saturated_fat_g':  require_float(item_data, 'saturated_fat_g'),
            'trans_fat_g':      require_float(item_data, 'trans_fat_g'),
            'estimated_gi':     require_float(item_data, 'estimated_gi'),
            'glycemic_load':    require_float(item_data, 'glycemic_load'),
            'sodium_mg':        require_float(item_data, 'sodium_mg'),
            'potassium_mg':     require_float(item_data, 'potassium_mg'),
            'iron_mg':          require_float(item_data, 'iron_mg'),
            'calcium_mg':       require_float(item_data, 'calcium_mg'),
            'iodine_mcg':       require_float(item_data, 'iodine_mcg'),
            'zinc_mg':          require_float(item_data, 'zinc_mg'),
            'magnesium_mg':     require_float(item_data, 'magnesium_mg'),
            'selenium_mcg':     require_float(item_data, 'selenium_mcg'),
            'cholesterol_mg':   require_float(item_data, 'cholesterol_mg'),
            'omega_3_g':        require_float(item_data, 'omega_3_g'),
            'vitamin_d_mcg':    require_float(item_data, 'vitamin_d_mcg'),
            'vitamin_b12_mcg':  require_float(item_data, 'vitamin_b12_mcg'),
            'fodmap_level':     (item_data.get('fodmap_level') or 'Low').title(),
            'spice_level':      (item_data.get('spice_level') or 'Low').title(),
            'purine_level':     (item_data.get('purine_level') or 'Low').title(),
            'is_verified':      False,
        }

        # Use name (case-insensitive get, then create/update by exact name)
        existing = FoodItem.objects.filter(
            name__iexact=standardized_name).first()
        if existing:
            # === Changes made by Ananya (Start) ===
            # 1) known-food attributes via attribute_matcher.py
            # 2) AI-generated attributes for foods not already linked by matcher
            # (Only applied if FoodItem has no existing attributes; no overwrite.)
            # === Changes made by Ananya (End) ===

            for attr, val in food_item_defaults.items():
                setattr(existing, attr, val)
            existing.save()
        # === Changes made by Ananya (Start) ===
        # 1) known-food attributes via attribute_matcher.py
            link_food_attributes(existing)
        # 2) AI-generated attributes for foods not already linked by matcher
            try:
                apply_gemini_attributes_to_food_if_missing(existing, data)
            except Exception:
                logger.exception(
                    "AI attribute application failed (existing FoodItem).")
                
        # === Changes made by Ananya (End) ===

            food_item_obj = existing
            created = False
        else:
            food_item_obj = FoodItem.objects.create(
                name=standardized_name,
                **food_item_defaults
            )
            link_food_attributes(food_item_obj)
            try:
               apply_gemini_attributes_to_food_if_missing(food_item_obj, data)
            except Exception:
                logger.exception("AI attribute application failed (new FoodItem).")

            created = True

        print(f"{'Created' if created else 'Updated'} FoodItem '{food_item_obj.name}': "
              f"cal={food_item_obj.calories} p={food_item_obj.protein} "
              f"c={food_item_obj.carbs} f={food_item_obj.fats}")

        food_types = [FoodType.objects.get_or_create(
            name=n.strip())[0] for n in data.get('food_types', [])]
        meal_types = [MealType.objects.get_or_create(
            name=n.strip())[0] for n in data.get('meal_types', [])]
        allergens = [Allergen.objects.get_or_create(name=n.strip())[0] for n in data.get(
            'allergens', []) if n.lower().strip() not in ('none', '')]
        food_item_obj.food_types.set(food_types)
        food_item_obj.meal_types.set(meal_types)
        food_item_obj.allergens.set(allergens)
        return food_item_obj

    except json.JSONDecodeError:
        print(
            f"❌ Gemini JSON Decode Error for '{food_query}'. Raw text:\n{response.text}")
        raise ValueError(
            f"Could not parse nutrition data from AI. Invalid JSON.")
    except Exception as e:
        err_str = str(e).lower()
        if any(code in err_str for code in ("503", "unavailable", "429", "resource_exhausted", "timeout", "deadline")):
            raise GeminiUnavailableError(
                f"Gemini temporarily unavailable for '{food_query}': {e}")
        traceback.print_exc()
        raise ValueError(
            f"An API or database error occurred for '{food_query}': {e}")


# Helper function (place in a utils.py file or above the main function)
def get_nullable_float2(data_dict: dict, key: str) -> float | None:
    """
    Safely gets a float from a dictionary key. Handles numbers, string-numbers,
    and None values. Returns None if conversion fails.
    """
    value = data_dict.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@transaction.atomic
def food_search_gemini(food_query: str) -> FoodItem:
    """
    (FINAL CORRECTED VERSION)
    Fetches a COMPLETE nutritional profile by parsing a natural language query.
    Relies on Gemini to identify the quantity, unit, and food from the query string
    (e.g., "1 piece of roti") and calculate the nutrition for that exact serving.

    Args:
        food_query (str): The user's full search query, including quantity and unit.

    Returns:
        The created or updated FoodItem model instance containing the nutritional
        data for the specified portion.
    """
    if not food_query:
        raise ValueError("Food query cannot be empty.")

    # --- THE PROMPT IS NOW RE-ENGINEERED TO PARSE THE QUERY ---
    prompt = f"""
Provide the most accurate and COMPLETE nutritional information for the user's query: "{food_query}".

🔥 CRITICAL INSTRUCTIONS FOR ACCURACY AND PARSING:
1) Intelligent Parsing: From the user's query ("{food_query}"), identify the quantity, unit, and food composition. The nutrition MUST correspond exactly to this parsed serving.
2) Source Reliability: Base values ONLY on reputable databases (e.g., USDA).
3) Preserve Name EXACTLY: In the 'name' field, keep the user’s food name as-is (you may fix capitalization only). 
   - Example: "cabbage and bajra roti and peanuts" → name = "Cabbage and Bajra Roti and Peanuts".
   - NEVER replace ingredients or reinterpret the dish (do NOT turn cabbage into peas, do NOT change “roti” to “flatbread,” etc.).
4) Composition Handling: If the query adds components (e.g., “and peanuts”), retain the base dish and ADD the new component’s nutrients so totals reflect the full composition.
5) Data Completeness: Provide a value for EVERY key in the JSON structure. If a reliable value cannot be found, use numeric 0. Do not omit keys.
6) JSON Only: Output a single valid JSON object, no extra text or markdown.

JSON Structure (Reflecting the parsed query):
{{
  "source_url": "<URL of the data source, if available>",
  "food_item": {{
    "name": "<The standardized name of the food, e.g., 'Roti', 'Paneer'>",
    "default_quantity": "<The numeric quantity you parsed from the query>",
    "default_unit": "<The unit you parsed from the query, e.g., 'piece', 'gram', 'cup'>",
    "gram_equivalent": "<The gram weight of the parsed serving>",
    "calories": "<number>",
    "protein": "<number>",
    "carbs": "<number>",
    "fats": "<number>",
    "sugar": "<number>",
    "fiber": "<number>",
    "saturated_fat_g": "<number>",
    "trans_fat_g": "<number>",
    "estimated_gi": "<number>",
    "glycemic_load": "<number>",
    "sodium_mg": "<number>",
    "potassium_mg": "<number>",
    "iron_mg": "<number>",
    "calcium_mg": "<number>",
    "iodine_mcg": "<number>",
    "zinc_mg": "<number>",
    "magnesium_mg": "<number>",
    "selenium_mcg": "<number>",
    "cholesterol_mg": "<number>",
    "omega_3_g": "<number>",
    "vitamin_d_mcg": "<number>",
    "vitamin_b12_mcg": "<number>",
    "fodmap_level": "<Low|Medium|High|None>",
    "spice_level": "<Low|Medium|High|None>",
    "purine_level": "<Low|Medium|High|None>"
  }},
  "food_types": ["<Vegetarian|Non-Vegetarian|Vegan>"],
  "meal_types": ["<Breakfast|Lunch|Dinner|Snack>"],
  "allergens": ["<Gluten|Dairy|Nuts|None>", "..."]
}}
"""
    try:
        print(
            f"🔄 Querying Gemini with natural language query: '{food_query}'...")
        start_time = time.time()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        )

        elapsed_time = time.time() - start_time
        logger.warning(
            f"⏱️ Gemini response time (nutrition): {elapsed_time:.2f}s | food='{food_query}'")

        data = json.loads(response.text)
        item_data = data.get("food_item")
        if not item_data:
            raise ValueError(
                "JSON response from Gemini missing 'food_item' object.")

        # Use the standardized name from Gemini; this is the key for our database entry.
        standardized_name = item_data.get('name', food_query).strip()
        if not standardized_name:  # Ensure the name is not empty
            raise ValueError("Gemini response provided an empty food name.")

        # Build the defaults dictionary. This robustly handles the parsed data from Gemini.
        # It defaults all numeric fields to 0.0 as a final safeguard.
        food_item_defaults = {
            'source_url': data.get('source_url'),
            # These values are now parsed BY Gemini
            'default_quantity': get_nullable_float2(item_data, 'default_quantity') or 1.0,
            'default_unit': item_data.get('default_unit') or 'serving',
            'gram_equivalent': get_nullable_float2(item_data, 'gram_equivalent') or 0.0,

            # Nutritional data
            'calories': get_nullable_float2(item_data, 'calories') or 0.0,
            'protein': get_nullable_float2(item_data, 'protein') or 0.0,
            'carbs': get_nullable_float2(item_data, 'carbs') or 0.0,
            'fats': get_nullable_float2(item_data, 'fats') or 0.0,
            'sugar': get_nullable_float2(item_data, 'sugar') or 0.0,
            'fiber': get_nullable_float2(item_data, 'fiber') or 0.0,
            'saturated_fat_g': get_nullable_float2(item_data, 'saturated_fat_g') or 0.0,
            'trans_fat_g': get_nullable_float2(item_data, 'trans_fat_g') or 0.0,
            'estimated_gi': get_nullable_float2(item_data, 'estimated_gi') or 0.0,
            'glycemic_load': get_nullable_float2(item_data, 'glycemic_load') or 0.0,
            'sodium_mg': get_nullable_float2(item_data, 'sodium_mg') or 0.0,
            'potassium_mg': get_nullable_float2(item_data, 'potassium_mg') or 0.0,
            'iron_mg': get_nullable_float2(item_data, 'iron_mg') or 0.0,
            'calcium_mg': get_nullable_float2(item_data, 'calcium_mg') or 0.0,
            'iodine_mcg': get_nullable_float2(item_data, 'iodine_mcg') or 0.0,
            'zinc_mg': get_nullable_float2(item_data, 'zinc_mg') or 0.0,
            'magnesium_mg': get_nullable_float2(item_data, 'magnesium_mg') or 0.0,
            'selenium_mcg': get_nullable_float2(item_data, 'selenium_mcg') or 0.0,
            'cholesterol_mg': get_nullable_float2(item_data, 'cholesterol_mg') or 0.0,
            'omega_3_g': get_nullable_float2(item_data, 'omega_3_g') or 0.0,
            'vitamin_d_mcg': get_nullable_float2(item_data, 'vitamin_d_mcg') or 0.0,
            'vitamin_b12_mcg': get_nullable_float2(item_data, 'vitamin_b12_mcg') or 0.0,

            # Categorical data
            'fodmap_level': (item_data.get('fodmap_level') or 'Low').title(),
            'spice_level': (item_data.get('spice_level') or 'Low').title(),
            'purine_level': (item_data.get('purine_level') or 'Low').title(),
            'is_verified': False,  # New items from AI are always unverified
        }

        # The `update_or_create` will find a food by its standardized name (e.g., "Roti")
        # and update it with the nutritional data for the latest query (e.g., "2 piece roti").
        food_item_obj, created = FoodItem.objects.update_or_create(
            name__iexact=standardized_name,
            defaults={'name': standardized_name, **food_item_defaults}
        )
        link_food_attributes(food_item_obj)

        log_prefix = "✅ Created" if created else "✅ Updated"
        print(f"{log_prefix} food item '{food_item_obj.name}' with data for {food_item_obj.default_quantity} {food_item_obj.default_unit}.")

        # Handle M2M relationships (this logic remains correct)
        food_types = [FoodType.objects.get_or_create(
            name=name.strip())[0] for name in data.get('food_types', [])]
        meal_types = [MealType.objects.get_or_create(
            name=name.strip())[0] for name in data.get('meal_types', [])]
        allergens = [Allergen.objects.get_or_create(name=name.strip())[0] for name in data.get(
            'allergens', []) if name.lower().strip() not in ('none', '')]

        food_item_obj.food_types.set(food_types)
        food_item_obj.meal_types.set(meal_types)
        food_item_obj.allergens.set(allergens)

        return food_item_obj

    except json.JSONDecodeError:
        print(
            f"❌ Gemini JSON Decode Error for '{food_query}'. Raw text:\n{response.text}")
        raise ValueError(
            f"Could not parse nutrition data from AI. Invalid JSON.")
    except Exception as e:
        traceback.print_exc()
        raise ValueError(
            f"An API or database error occurred for '{food_query}': {e}")


# ================================================================
# APPEND THIS ENTIRE BLOCK to the bottom of your utils/gemini.py
# ================================================================

def suggest_foods_gemini(remaining_nutrients: dict, user_profile, meal_type: str = None):
    """
    Fallback: ask Gemini for food suggestions when the DB pool is too small.
    Uses the same google.genai client already initialised at the top of gemini.py.
    Creates / updates FoodItem records so they are cached for future requests.
    Returns list of FoodItem instances.
    """
    import json as _json
    from userFood.models import FoodItem, FoodType, MealType, Allergen

    diet_type = getattr(user_profile, "diet_type",   "Any") or "Any"
    country = getattr(user_profile, "country",     "India") or "India"
    allergies = getattr(user_profile, "allergies",   "None") or "None"
    is_diabetic = bool(getattr(user_profile, "is_diabetic", False))

    meal_hint = f"for {meal_type}" if meal_type else "for any meal"

    prompt = f"""
You are a clinical nutritionist AI. Suggest 5 whole-food meal options {meal_hint}
for a person with the following profile:
- Remaining calories today : {remaining_nutrients.get('calories', 400)} kcal
- Remaining protein today  : {remaining_nutrients.get('protein_g', 25)}g
- Diet type                : {diet_type}
- Country / cuisine pref   : {country}
- Allergies                : {allergies}
- Diabetic                 : {is_diabetic}

Rules:
1. Suggest region-appropriate foods for {country}.
2. Respect diet type — no Non-Vegetarian items if diet is vegetarian/vegan.
3. Each food's calories MUST be <= {remaining_nutrients.get('calories', 400) * 0.75:.0f} kcal.
4. If diabetic, keep estimated_gi < 55.
5. Return ONLY a valid JSON array of exactly 5 objects. No markdown, no preamble.

Each object must use these exact keys:
{{
  "name": "<food name>",
  "default_quantity": <float>,
  "default_unit": "<piece|cup|bowl|g>",
  "gram_equivalent": <float or null>,
  "calories": <float>,
  "protein": <float>,
  "carbs": <float>,
  "fats": <float>,
  "fiber": <float or null>,
  "sugar": <float or null>,
  "saturated_fat_g": <float or null>,
  "trans_fat_g": <float or null>,
  "estimated_gi": <float or null>,
  "glycemic_load": <float or null>,
  "sodium_mg": <float or null>,
  "potassium_mg": <float or null>,
  "iron_mg": <float or null>,
  "calcium_mg": <float or null>,
  "iodine_mcg": <float or null>,
  "zinc_mg": <float or null>,
  "magnesium_mg": <float or null>,
  "selenium_mcg": <float or null>,
  "cholesterol_mg": <float or null>,
  "omega_3_g": <float or null>,
  "vitamin_d_mcg": <float or null>,
  "vitamin_b12_mcg": <float or null>,
  "fodmap_level": "<Low|Medium|High|None>",
  "spice_level": "<Low|Medium|High|None>",
  "purine_level": "<Low|Medium|High|None>",
  "food_types": ["<Vegetarian|Non-Vegetarian|Vegan>"],
  "meal_types": ["<Breakfast|Lunch|Dinner|Snack>"],
  "allergens": ["<name>"]
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )

        raw = response.text.strip()
        # Strip markdown fences if model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        items = _json.loads(raw)
        if not isinstance(items, list):
            return []

        food_objects = []
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue

            defaults = {
                "default_quantity":  get_nullable_float(item, "default_quantity") or 1.0,
                "default_unit":      item.get("default_unit") or "serving",
                "gram_equivalent":   get_nullable_float(item, "gram_equivalent"),
                "calories":          get_nullable_float(item, "calories") or 0.0,
                "protein":           get_nullable_float(item, "protein") or 0.0,
                "carbs":             get_nullable_float(item, "carbs") or 0.0,
                "fats":              get_nullable_float(item, "fats") or 0.0,
                "fiber":             get_nullable_float(item, "fiber"),
                "sugar":             get_nullable_float(item, "sugar"),
                "saturated_fat_g":   get_nullable_float(item, "saturated_fat_g"),
                "trans_fat_g":       get_nullable_float(item, "trans_fat_g"),
                "estimated_gi":      get_nullable_float(item, "estimated_gi"),
                "glycemic_load":     get_nullable_float(item, "glycemic_load"),
                "sodium_mg":         get_nullable_float(item, "sodium_mg"),
                "potassium_mg":      get_nullable_float(item, "potassium_mg"),
                "iron_mg":           get_nullable_float(item, "iron_mg"),
                "calcium_mg":        get_nullable_float(item, "calcium_mg"),
                "iodine_mcg":        get_nullable_float(item, "iodine_mcg"),
                "zinc_mg":           get_nullable_float(item, "zinc_mg"),
                "magnesium_mg":      get_nullable_float(item, "magnesium_mg"),
                "selenium_mcg":      get_nullable_float(item, "selenium_mcg"),
                "cholesterol_mg":    get_nullable_float(item, "cholesterol_mg"),
                "omega_3_g":         get_nullable_float(item, "omega_3_g"),
                "vitamin_d_mcg":     get_nullable_float(item, "vitamin_d_mcg"),
                "vitamin_b12_mcg":   get_nullable_float(item, "vitamin_b12_mcg"),
                "fodmap_level":      (item.get("fodmap_level") or "Low").title(),
                "spice_level":       (item.get("spice_level") or "Low").title(),
                "purine_level":      (item.get("purine_level") or "Low").title(),
                "is_verified":       False,
            }

            food_obj, _ = FoodItem.objects.update_or_create(
                name__iexact=name,
                defaults={"name": name, **defaults},
            )
            link_food_attributes(food_obj)

            # M2M
            ft_objs = [FoodType.objects.get_or_create(name=n.strip())[0]
                       for n in item.get("food_types", []) if n.strip()]
            mt_objs = [MealType.objects.get_or_create(name=n.strip())[0]
                       for n in item.get("meal_types", []) if n.strip()]
            al_objs = [Allergen.objects.get_or_create(name=n.strip())[0]
                       for n in item.get("allergens", [])
                       if n.strip().lower() not in ("none", "")]

            if ft_objs:
                food_obj.food_types.set(ft_objs)
            if mt_objs:
                food_obj.meal_types.set(mt_objs)
            if al_objs:
                food_obj.allergens.set(al_objs)

            food_objects.append(food_obj)

        return food_objects

    except Exception as exc:
        logger.warning(f"suggest_foods_gemini error: {exc}")
        return []
