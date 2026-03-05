# ml_model/src/generator.py

# ================================
# 🔹 Required Library Imports
# ================================
import torch
import pandas as pd
import json
import os
import random
from collections import defaultdict
import numpy as np

# ================================
# 🔹 Import Custom Modules
# ================================
from .model import Encoder, Decoder, Seq2Seq
from .rule_engine import get_allowed_foods

# ================================
# 🔹 Import Django ORM Models (with robust mocking)
# ================================
try:
    from user.models import User
    from userProfile.models import UserProfile, LabReport
except ImportError:
    print("⚠️ WARNING: Django models not found. Using mock objects for demonstration.")
    from unittest.mock import Mock, MagicMock
    User, UserProfile, LabReport = Mock(), Mock(), Mock()
    User.objects, UserProfile.objects, LabReport.objects = MagicMock(), MagicMock(), MagicMock()

# ================================
# 🔸 Initialization Logs & Configuration
# ================================
print("AI DIET PLANNER (OPTIMIZER V4 with CONTEXT-AWARE TEMPLATES): Initializing...")
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SRC_DIR)

V2_MODEL_PATH = os.path.join(BASE_DIR, 'saved_models', 'diet_model_v2.pth')
V1_MODEL_PATH = os.path.join(BASE_DIR, 'saved_models', f'diet_model_v1_epoch_79.pth')
MODEL_PATH = V2_MODEL_PATH if os.path.exists(V2_MODEL_PATH) else V1_MODEL_PATH
MODEL_VERSION = 'v2' if os.path.exists(V2_MODEL_PATH) else 'v1'
print(f"✅ Using model '{MODEL_VERSION}': {MODEL_PATH}")

VOCAB_FILE = os.path.join(BASE_DIR, 'saved_models', 'food_vocab.json')
FOOD_DATA_FILE = os.path.join(BASE_DIR, 'data', 'food_items.xlsx')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

PLAN_DAYS = 15
MEAL_NAMES = ['Early-Morning', 'Breakfast', 'Mid-Morning Snack', 'Lunch', 'Afternoon Snack', 'Dinner', 'Bedtime']
TOP_K = 50

# ⭐️⭐️⭐️ EXPERT UPGRADE: CONTEXT-AWARE MEAL TEMPLATES ⭐️⭐️⭐️
# Each template is now an object with 'items' and 'tags' to enforce meal integrity.
# 'veg_only': Ensures no non-veg items are chosen, even for a non-veg user.
# 'non_veg_only': Ensures the main dish is non-vegetarian.
# 'any': Can be filled with any allowed food.
MEAL_TEMPLATES = {
    'Early-Morning': [
        {'items': ['Morning Drink', 'Dry Fruit and Nut'], 'tags': ['any']},
        {'items': ['Morning Drink'], 'tags': ['any']},
        {'items': ['Dry Fruit and Nut'], 'tags': ['any']}
    ],
    'Breakfast': [
        {'items': ['Breakfast Dish', 'Juice'], 'tags': ['veg_only']},
        {'items': ['Breakfast Dish'], 'tags': ['veg_only']},
        {'items': ['Juice', 'Dry Fruit and Nut'], 'tags': ['any']}
    ],
    'Mid-Morning Snack': [
        {'items': ['Smoothie', 'Fruit'], 'tags': ['any']},
        {'items': ['Fruit', 'Juice'], 'tags': ['any']},
        {'items': ['Fruit'], 'tags': ['any']}
    ],
    'Lunch': [
        {'items': ['Dal', 'Sabzi', 'Roti', 'Rice', 'Sider'], 'tags': ['veg_only']},
        {'items': ['Non-veg sabzi', 'Roti', 'Rice', 'Salad'], 'tags': ['non_veg_only']},
        {'items': ['One Pot Meal', 'Raita'], 'tags': ['any']},
        {'items': ['Paratha', 'Curd', 'Salad'], 'tags': ['veg_only']}
    ],
    'Afternoon Snack': [
        {'items': ['Snack'], 'tags': ['any']},
        {'items': ['Dry Fruit and Nut'], 'tags': ['any']},
        {'items': ['Smoothie'], 'tags': ['any']}
    ],
    'Dinner': [
        {'items': ['Sabzi', 'Roti', 'Salad'], 'tags': ['veg_only']},
        {'items': ['Non-veg sabzi', 'Roti', 'Salad'], 'tags': ['non_veg_only']},
        {'items': ['One Pot Meal', 'Raita'], 'tags': ['any']},
        {'items': ['Soup'], 'tags': ['any']}
    ],
    'Bedtime': [
        {'items': ['Night Drink'], 'tags': ['any']}
    ]
}


# ================================
# 🔸 Load Vocabulary, Model, and Food Data
# ================================
try:
    with open(VOCAB_FILE, 'r') as f: food_vocab = json.load(f)
    inv_food_vocab = {v: k for k, v in food_vocab.items()}
    OUTPUT_DIM = len(food_vocab)
except FileNotFoundError: raise RuntimeError(f"FATAL: Missing vocabulary file: {VOCAB_FILE}. Cannot proceed.")
NUMERICAL_COLS = ['Age','Weight (kg)','Height (cm)','BMI (auto-calculated)','Waist Circumference (cm)','Fasting Blood Sugar (mg/dL)','HbA1c (%)','Postprandial Sugar (mg/dL)','LDL (mg/dL)','HDL (mg/dL)','Triglycerides (mg/dL)','CRP (mg/L)','ESR (mm/hr)','Uric Acid (mg/dL)','Creatinine (mg/dL)','Urea (mg/dL)','ALT (U/L)','AST (U/L)','Vitamin D3 (ng/mL)','Vitamin B12 (pg/mL)','TSH (uIU/mL)']
INPUT_DIM = len(NUMERICAL_COLS)
try:
    encoder = Encoder(INPUT_DIM, 256, 512)
    decoder = Decoder(OUTPUT_DIM, 256, 512)
    model = Seq2Seq(encoder, decoder, DEVICE).to(DEVICE)
    checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
    state_dict = checkpoint.get('model_state_dict', checkpoint)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"✅ Model '{MODEL_VERSION}' loaded successfully.")
except Exception as e: raise RuntimeError(f"FATAL: Error loading model from {MODEL_PATH}: {e}")
try:
    food_df = pd.read_excel(FOOD_DATA_FILE)
    food_df.columns = [col.strip().split('/')[0] for col in food_df.columns]
    food_df['Food_Item'] = food_df['Food_Item'].str.strip()
    numeric_cols = ['Household_Weight_g', 'Min_Units', 'Max_Units', 'Calories', 'Protein', 'Carbs', 'Fats', 'Sugar', 'Fiber', 'Saturated_Fat', 'Trans_Fat', 'Sodium', 'Potassium', 'Omega_3']
    for col in numeric_cols:
        if col in food_df.columns: food_df[col] = pd.to_numeric(food_df[col], errors='coerce').fillna(0)
    if 'Is_One_Pot' in food_df.columns: food_df['Is_One_Pot'] = food_df['Is_One_Pot'].astype(str)
    food_df.set_index('Food_Item', inplace=True)
    print(f"✅ Loaded and processed {len(food_df)} unique food items.")
except FileNotFoundError: raise RuntimeError(f"FATAL: Food data file not found at {FOOD_DATA_FILE}.")
except Exception as e: raise RuntimeError(f"FATAL: Failed to load food file {FOOD_DATA_FILE}: {e}")

# =============================================================================
# ⭐️ Helper Functions
# =============================================================================
def calculate_daily_needs(user_report):
    age = user_report.get('Age', 30); weight = user_report.get('Weight (kg)', 70); height = user_report.get('Height (cm)', 170); gender = user_report.get('Gender', 'Male').lower(); activity = user_report.get('Activity Level', 'Sedentary').lower()
    if gender == 'male': bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else: bmr = 10 * weight + 6.25 * height - 5 * age - 161
    multipliers = {'sedentary': 1.2, 'lightly active': 1.375, 'moderately active': 1.55, 'very active': 1.725}
    multiplier = multipliers.get(activity.replace(" ", ""), 1.2)
    target_calories = bmr * multiplier
    return {'calories': target_calories, 'protein': (target_calories * 0.30) / 4, 'carbs': (target_calories * 0.40) / 4, 'fats': (target_calories * 0.30) / 9}

def is_in_category(food_categories_str, target_category):
    if pd.isna(food_categories_str): return False
    categories = [cat.strip().lower() for cat in food_categories_str.split('/')]
    return target_category.lower() in categories

# =============================================================================
# ⭐️⭐️⭐️ CONTEXT-AWARE Meal Construction ⭐️⭐️⭐️
# =============================================================================
def construct_meal(meal_name, ai_suggestion, food_pool_df, is_veg):
    all_templates = MEAL_TEMPLATES.get(meal_name, [])
    if not all_templates:
        print(f"WARNING: No templates for meal '{meal_name}'.")
        return []

    # 1. Filter templates based on user's dietary preference
    valid_templates = []
    if is_veg:
        # Vegetarians can only have 'veg_only' or 'any' tagged templates
        valid_templates = [t for t in all_templates if 'non_veg_only' not in t['tags']]
    else:
        # Non-vegetarians can have any template
        valid_templates = all_templates

    if not valid_templates:
        print(f"WARNING: No valid templates for meal '{meal_name}' for this user.")
        return []

    chosen_template_obj = random.choice(valid_templates)
    chosen_template_items = chosen_template_obj['items']
    tags = chosen_template_obj['tags']

    meal_composition = []
    
    # 2. Prepare a context-specific food pool based on template tags
    contextual_food_pool = food_pool_df
    if 'veg_only' in tags:
        # Even for a non-veg user, if the template is veg_only, we filter the pool
        contextual_food_pool = food_pool_df[~food_df['Food_Type'].str.contains("Non-Vegetarian", na=False, case=False)]

    # Helper to select food from the correct (contextual) pool
    def select_food(category, food_pool):
        category_foods = food_pool[food_pool['Category'].apply(lambda x: is_in_category(x, category))]
        return category_foods.sample(1).index[0] if not category_foods.empty else None

    # 3. Build the meal using the contextual food pool
    for category in chosen_template_items:
        selected_food = select_food(category, contextual_food_pool)
        if selected_food:
            meal_composition.append(selected_food)
            # Remove the chosen food to prevent repetition within the same meal
            contextual_food_pool = contextual_food_pool.drop(selected_food, errors='ignore')

    return meal_composition

# =============================================================================
# ⭐️ Portion Optimization and Main Generation Logic
# =============================================================================
def optimize_portions(meal_foods, remaining_targets):
    meal_details, num_items = [], len(meal_foods)
    if not meal_foods: return [], remaining_targets
    calories_per_item = remaining_targets['calories'] / num_items if num_items > 0 else 0
    for food_name in meal_foods:
        if food_name not in food_df.index: continue
        food_info = food_df.loc[food_name]
        base_calories = food_info['Calories']
        num_units = round(calories_per_item / base_calories) if base_calories > 0 else food_info.get('Min_Units', 1)
        num_units = int(max(food_info.get('Min_Units', 1), min(num_units, food_info.get('Max_Units', 5))))
        final_nutrition = {"food_name": food_name, "quantity": num_units, "unit": food_info.get('Display_Unit', 'unit'), "calories": food_info['Calories'] * num_units, "protein": food_info['Protein'] * num_units, "carbs": food_info['Carbs'] * num_units, "fats": food_info['Fats'] * num_units}
        meal_details.append(final_nutrition)
        for key in ['calories', 'protein', 'carbs', 'fats']: remaining_targets[key] -= final_nutrition[key]
    return meal_details, remaining_targets

def generate_diet_plan(user_id):
    if not all([model, not food_df.empty, food_vocab]): return {"error": "AI system not fully initialized."}
    try:
        auth_user = User.objects.get(id=user_id)
        user_profile = UserProfile.objects.get(user=auth_user)
        lab_report = LabReport.objects.filter(user=auth_user).last()
        features = {**user_profile.__dict__, **(lab_report.__dict__ if lab_report else {})}
        user_report_series = pd.Series(features)
        input_tensor = torch.tensor(user_report_series.reindex(NUMERICAL_COLS).fillna(0).values, dtype=torch.float32).unsqueeze(0).to(DEVICE)
        is_veg = user_report_series.get('Dietary Preference', 'Vegetarian').lower() != 'non-vegetarian'
        daily_targets = calculate_daily_needs(user_report_series)
        allowed_foods_df_full, suggestion_flags = get_allowed_foods(user_report_series, food_df.reset_index())
        allowed_foods_df_full.set_index('Food_Item', inplace=True)
        allowed_food_names = set(allowed_foods_df_full.index) & set(food_vocab.keys())
        if len(allowed_food_names) < 20: return {"error": f"Not enough food variety ({len(allowed_food_names)} items) after rules."}
        allowed_ids = [food_vocab[name] for name in allowed_food_names]
        with torch.no_grad(): outputs = model.generate(input_tensor, meal_names=MEAL_NAMES * PLAN_DAYS, top_k=TOP_K, allowed_ids=allowed_ids)
        ai_suggestions = [inv_food_vocab.get(oid, "Unknown") for oid in outputs]
        final_plan = {}
        suggestion_idx = 0
        for day in range(1, PLAN_DAYS + 1):
            daily_plan, daily_totals = {}, defaultdict(float)
            remaining_targets_for_day = daily_targets.copy()
            allowed_foods_for_day = allowed_foods_df_full.copy()
            for meal_name in MEAL_NAMES:
                if suggestion_idx >= len(ai_suggestions): break
                ai_suggestion = ai_suggestions[suggestion_idx]
                suggestion_idx += 1
                meal_foods = construct_meal(meal_name, ai_suggestion, allowed_foods_for_day, is_veg)
                meal_details, remaining_targets_for_day = optimize_portions(meal_foods, remaining_targets_for_day)
                daily_plan[meal_name] = meal_details
                for item in meal_details:
                    for key in ['calories', 'protein', 'carbs', 'fats']: daily_totals[key] += item[key]
            daily_plan['daily_totals'] = {k: round(v, 2) for k, v in daily_totals.items()}
            daily_plan['daily_targets'] = {k: round(v, 2) for k, v in daily_targets.items()}
            final_plan[f"Day {day}"] = daily_plan
        final_plan["suggestion_flags"] = suggestion_flags
        return final_plan
    except User.DoesNotExist: return {"error": f"User with ID {user_id} not found."}
    except UserProfile.DoesNotExist: return {"error": f"User profile for user ID {user_id} is missing."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"An unexpected error occurred: {e}"}