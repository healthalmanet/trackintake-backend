import json
import traceback

import google.generativeai as genai
from django.db import transaction

from google import genai
from django.db import transaction
import time
import logging
import dotenv
import os
dotenv.load_dotenv()
logger = logging.getLogger(__name__)


# Import your Django models from the same app
from userFood.models import FoodItem, FoodType, MealType, Allergen, LEVEL_CHOICES

# --- Gemini API Configuration ---
# WARNING: Hardcoding API keys is not secure for production.
# It is better to use environment variables.
# However, per your request, the key is placed directly here.

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY not found in environment")

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
    """
    (FINAL CORRECTED VERSION)
    Fetches a COMPLETE nutritional profile. This version forces the AI to return 0
    for unknown values and ensures the Python code saves 0.0 instead of NULL.
    """
    food_query = f"{quantity} {unit} of {food_name}"
    
    # --- PROMPT UPDATED WITH A STRONGER, MORE FORCEFUL INSTRUCTION ---
    prompt = f"""
Return nutrition data for:
"{food_query}"

Rules:
- Match the exact serving
- Use reliable nutrition data (USDA-style)
- Use numeric 0 if a value is unknown or not present
- Do not omit any keys
- Output JSON only, no extra text

JSON Structure (MUST include all possible fields):
{{
  "source_url": "<URL of the data source, if available>",
  "food_item": {{
    "name": "<Standardized name of the food>",
    "default_quantity": {quantity},
    "default_unit": "{unit}",
    "gram_equivalent": "<number>",
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
    "fodmap_level": "<Low|Medium|High|Moderate|Mild|None>",
    "spice_level": "<Low|Medium|High|Moderate|Mild|None>",
    "purine_level": "<Low|Medium|High|Moderate|Mild|None>"
  }},
  "food_types": ["<Vegetarian|Non-Vegetarian|Vegan>"],
  "meal_types": ["<Breakfast|Lunch|Dinner|Snack>"],
  "allergens": ["<Gluten|Dairy|Nuts|None>", "..."]
}}
"""
    try:
        print(f"🔄 Fallback: Querying Gemini API for a complete profile of '{food_query}'...")

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
        logger.warning(f"⏱️ Gemini response time (nutrition): {elapsed_time:.2f}s | food='{food_query}'")
        logger.warning(response)

        data = json.loads(response.text)
        item_data = data.get("food_item")
        if not item_data:
            raise ValueError("JSON response from Gemini missing 'food_item' object.")

        standardized_name = item_data.get('name', food_name).strip()

        # --- PYTHON CODE IS NOW MORE ROBUST: DEFAULTS ALL NUMERIC FIELDS TO 0.0 ---
        # This ensures that even if the AI disobeys and omits a key, your database
        # will store 0.0 instead of NULL.
        food_item_defaults = {
            'default_quantity': get_nullable_float(item_data, 'default_quantity') or quantity,
            'default_unit': item_data.get('default_unit') or unit,
            'gram_equivalent': get_nullable_float(item_data, 'gram_equivalent') or 0.0,
            'source_url': data.get('source_url'),
            'calories': get_nullable_float(item_data, 'calories') or 0.0,
            'protein': get_nullable_float(item_data, 'protein') or 0.0,
            'carbs': get_nullable_float(item_data, 'carbs') or 0.0,
            'fats': get_nullable_float(item_data, 'fats') or 0.0,
            'sugar': get_nullable_float(item_data, 'sugar') or 0.0,
            'fiber': get_nullable_float(item_data, 'fiber') or 0.0,
            'saturated_fat_g': get_nullable_float(item_data, 'saturated_fat_g') or 0.0,
            'trans_fat_g': get_nullable_float(item_data, 'trans_fat_g') or 0.0,
            'estimated_gi': get_nullable_float(item_data, 'estimated_gi') or 0.0,
            'glycemic_load': get_nullable_float(item_data, 'glycemic_load') or 0.0,
            'sodium_mg': get_nullable_float(item_data, 'sodium_mg') or 0.0,
            'potassium_mg': get_nullable_float(item_data, 'potassium_mg') or 0.0,
            'iron_mg': get_nullable_float(item_data, 'iron_mg') or 0.0,
            'calcium_mg': get_nullable_float(item_data, 'calcium_mg') or 0.0,
            'iodine_mcg': get_nullable_float(item_data, 'iodine_mcg') or 0.0,
            'zinc_mg': get_nullable_float(item_data, 'zinc_mg') or 0.0,
            'magnesium_mg': get_nullable_float(item_data, 'magnesium_mg') or 0.0,
            'selenium_mcg': get_nullable_float(item_data, 'selenium_mcg') or 0.0,
            'cholesterol_mg': get_nullable_float(item_data, 'cholesterol_mg') or 0.0,
            'omega_3_g': get_nullable_float(item_data, 'omega_3_g') or 0.0,
            'vitamin_d_mcg': get_nullable_float(item_data, 'vitamin_d_mcg') or 0.0,
            'vitamin_b12_mcg': get_nullable_float(item_data, 'vitamin_b12_mcg') or 0.0,
            'fodmap_level': (item_data.get('fodmap_level') or 'Low').title(),
            'spice_level': (item_data.get('spice_level') or 'Low').title(),
            'purine_level': (item_data.get('purine_level') or 'Low').title(),
            'is_verified': False,
        }

        food_item_obj, created = FoodItem.objects.update_or_create(
            name__iexact=standardized_name,
            defaults={'name': standardized_name, **food_item_defaults}
        )
        
        log_prefix = "✅ Created" if created else "✅ Updated"
        print(f"{log_prefix} food item via Gemini: '{food_item_obj.name}'")

        # Handle M2M relationships (no changes needed here)
        food_types = [FoodType.objects.get_or_create(name=name.strip())[0] for name in data.get('food_types', [])]
        meal_types = [MealType.objects.get_or_create(name=name.strip())[0] for name in data.get('meal_types', [])]
        allergens = [Allergen.objects.get_or_create(name=name.strip())[0] for name in data.get('allergens', []) if name.lower().strip() not in ('none', '')]
        
        food_item_obj.food_types.set(food_types)
        food_item_obj.meal_types.set(meal_types)
        food_item_obj.allergens.set(allergens)
        print(data)
        return food_item_obj

    except json.JSONDecodeError:
        print(f"❌ Gemini JSON Decode Error for '{food_query}'. Raw text:\n{response.text}")
        raise ValueError(f"Could not parse nutrition data from AI. Invalid JSON.")
    except Exception as e:
        traceback.print_exc()
        raise ValueError(f"An API or database error occurred for '{food_query}': {e}")











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
        print(f"🔄 Querying Gemini with natural language query: '{food_query}'...")
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
        logger.warning(f"⏱️ Gemini response time (nutrition): {elapsed_time:.2f}s | food='{food_query}'")


        data = json.loads(response.text)
        item_data = data.get("food_item")
        if not item_data:
            raise ValueError("JSON response from Gemini missing 'food_item' object.")

        # Use the standardized name from Gemini; this is the key for our database entry.
        standardized_name = item_data.get('name', food_query).strip()
        if not standardized_name: # Ensure the name is not empty
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
            'is_verified': False, # New items from AI are always unverified
        }

        # The `update_or_create` will find a food by its standardized name (e.g., "Roti")
        # and update it with the nutritional data for the latest query (e.g., "2 piece roti").
        food_item_obj, created = FoodItem.objects.update_or_create(
            name__iexact=standardized_name,
            defaults={'name': standardized_name, **food_item_defaults}
        )
        
        log_prefix = "✅ Created" if created else "✅ Updated"
        print(f"{log_prefix} food item '{food_item_obj.name}' with data for {food_item_obj.default_quantity} {food_item_obj.default_unit}.")

        # Handle M2M relationships (this logic remains correct)
        food_types = [FoodType.objects.get_or_create(name=name.strip())[0] for name in data.get('food_types', [])]
        meal_types = [MealType.objects.get_or_create(name=name.strip())[0] for name in data.get('meal_types', [])]
        allergens = [Allergen.objects.get_or_create(name=name.strip())[0] for name in data.get('allergens', []) if name.lower().strip() not in ('none', '')]
        
        food_item_obj.food_types.set(food_types)
        food_item_obj.meal_types.set(meal_types)
        food_item_obj.allergens.set(allergens)
        
        return food_item_obj

    except json.JSONDecodeError:
        print(f"❌ Gemini JSON Decode Error for '{food_query}'. Raw text:\n{response.text}")
        raise ValueError(f"Could not parse nutrition data from AI. Invalid JSON.")
    except Exception as e:
        traceback.print_exc()
        raise ValueError(f"An API or database error occurred for '{food_query}': {e}")