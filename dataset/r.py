import os
import django
import pandas as pd
from django.core.exceptions import ValidationError
from django.db import IntegrityError
import sys

# --- Django Setup ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

django.setup()

from app.models import FoodItem  # 🔁 Change to your app name

# --- Config ---
FILE_PATH = 'data/food_items.xlsx'  # <-- update to the actual relative path

COLUMN_MAPPING = {
    'Food_Item': 'name',
    'Default_Quantity': 'default_quantity',
    'Default_Type': 'default_unit',
    'Gram_Equivalent': 'gram_equivalent',
    'Calories': 'calories',
    'Protein': 'protein',
    'Carbs': 'carbs',
    'Fats': 'fats',
    'Sugar': 'sugar',
    'Fiber': 'fiber',
    'Saturated_Fat/g': 'saturated_fat_g',
    'Trans_Fat/g': 'trans_fat_g',
    'Estimated_GI': 'estimated_gi',
    'Glycemic_Load': 'glycemic_load',
    'Sodium/mg': 'sodium_mg',
    'Potassium/mg': 'potassium_mg',
    'Iron/mg': 'iron_mg',
    'Calcium/mg': 'calcium_mg',
    'Iodine/mcg': 'iodine_mcg',
    'Zinc/mg': 'zinc_mg',
    'Magnesium/mg': 'magnesium_mg',
    'Selenium/mcg': 'selenium_mcg',
    'Cholesterol/mg': 'cholesterol_mg',
    'Omega_3/g': 'omega_3_g',
    'Vitamin_D/mcg': 'vitamin_d_mcg',
    'Vitamin_B12/mcg': 'vitamin_b12_mcg',
    'Vegetarian': 'food_type',
    'Meal_Type': 'meal_type',
    'FODMAP_Level': 'fodmap_level',
    'Spice_Level': 'spice_level',
    'Purine_Level': 'purine_level',
    'Allergens': 'allergens',
}

# --- Helpers ---
def process_default(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def process_name(value):
    return str(value).strip() if pd.notna(value) else None

def process_default_unit(value):
    return str(value).strip().lower() if pd.notna(value) else "piece"

def process_float(value):
    if pd.isna(value) or str(value).strip().lower() in ['', 'none']:
        return None
    try:
        return float(str(value).replace(' ', ''))
    except Exception:
        return None

def process_food_type(value):
    v = str(value).strip().lower()
    if not v or v == 'none':
        return "other"
    if "non-veg" in v: return "non_vegetarian"
    if "egg" in v: return "eggetarian"
    if "vegan" in v: return "vegan"
    if "veg" in v: return "vegetarian"
    return "other"

def process_meal_type(value):
    if pd.isna(value): return []
    valid_choices = {choice[0] for choice in FoodItem.MEAL_TYPE_CHOICES}
    term_map = {
        "early morning": "early_morning",
        "mid-morning snack": "morning_snack",
        "afternoon snack": "evening_snack"
    }
    parts = str(value).replace('/', ' ').replace(',', ' ').split()
    processed_parts = []
    for part in parts:
        clean = part.strip().lower()
        if clean in term_map: processed_parts.append(term_map[clean])
        elif clean.replace('_', ' ') in term_map: processed_parts.append(term_map[clean.replace('_', ' ')])
        elif clean.replace(' ', '_') in valid_choices: processed_parts.append(clean.replace(' ', '_'))
        elif clean in valid_choices: processed_parts.append(clean)
    return list(set(processed_parts))

def process_level(value):
    v = str(value).strip().lower()
    if v == 'moderate': return 'medium'
    if v == 'mild': return 'low'
    valid_choices = {"low", "medium", "high", "none"}
    return v if v in valid_choices else "low"

# Map processors
float_fields = [
    'default_quantity', 'gram_equivalent', 'calories', 'protein', 'carbs', 'fats', 'sugar', 'fiber',
    'saturated_fat_g', 'trans_fat_g', 'estimated_gi', 'glycemic_load', 'sodium_mg', 'potassium_mg',
    'iron_mg', 'calcium_mg', 'iodine_mcg', 'zinc_mg', 'magnesium_mg', 'selenium_mcg',
    'cholesterol_mg', 'omega_3_g', 'vitamin_d_mcg', 'vitamin_b12_mcg'
]

processors = {
    'name': process_name,
    'default_unit': process_default_unit,
    'food_type': process_food_type,
    'meal_type': process_meal_type,
    'fodmap_level': process_level,
    'spice_level': process_level,
    'purine_level': process_level,
    'allergens': process_default,
}
for f in float_fields:
    processors[f] = process_float

# --- Main Import Logic ---
if not os.path.exists(FILE_PATH):
    print(f"❌ File not found: {FILE_PATH}")
    exit()

df = pd.read_excel(FILE_PATH, engine='openpyxl')
df.rename(columns={k: v for k, v in COLUMN_MAPPING.items() if k in df.columns}, inplace=True)

existing_names = set(FoodItem.objects.values_list('name', flat=True))
items_to_create = []
errors = []
skipped = 0

for index, row in df.iterrows():
    data = {}
    for field in COLUMN_MAPPING.values():
        raw = row.get(field)
        processor = processors.get(field, process_default)
        data[field] = processor(raw)

    if not data.get("name"):
        errors.append(f"Row {index+2}: missing name")
        continue

    if data['name'] in existing_names:
        skipped += 1
        continue

    try:
        item = FoodItem(**data)
        item.full_clean()
        items_to_create.append(item)
        existing_names.add(item.name)
    except ValidationError as ve:
        msg = ', '.join([f"{k}: {', '.join(v)}" for k, v in ve.message_dict.items()])
        errors.append(f"Row {index+2} ({data['name']}): {msg}")
    except Exception as e:
        errors.append(f"Row {index+2} ({data['name']}): {e}")

# Save to DB
if items_to_create:
    try:
        FoodItem.objects.bulk_create(items_to_create, batch_size=500)
        print(f"✅ Imported {len(items_to_create)} items")
    except Exception as e:
        print(f"❌ Failed bulk create: {e}")

if skipped:
    print(f"⚠️ Skipped {skipped} existing items")

if errors:
    print(f"❌ {len(errors)} errors:")
    for err in errors[:10]:
        print(" -", err)
    if len(errors) > 10:
        print(f"   ... and {len(errors)-10} more")
