# ml_model/1_prepare_bootstrap_data.py

# 🔹 Import required libraries
import pandas as pd
import numpy as np
import json
import re # Import regex for safer string matching
from src.rule_engine import get_allowed_foods
from tqdm import tqdm
import os

# 🔸 Configuration constants
NUM_PLANS_PER_USER = 50
PLAN_DAYS = 15
MEALS_PER_DAY = 7
SEQUENCE_LENGTH = PLAN_DAYS * MEALS_PER_DAY

# 🔸 Columns representing the user’s numerical health data (must match model training)
NUMERICAL_COLS = [
    'Age', 'Weight (kg)', 'Height (cm)', 'BMI (auto-calculated)', 'Waist Circumference (cm)',
    'Fasting Blood Sugar (mg/dL)', 'HbA1c (%)', 'Postprandial Sugar (mg/dL)', 'LDL (mg/dL)',
    'HDL (mg/dL)', 'Triglycerides (mg/dL)', 'CRP (mg/L)', 'ESR (mm/hr)', 'Uric Acid (mg/dL)',
    'Creatinine (mg/dL)', 'Urea (mg/dL)', 'ALT (U/L)', 'AST (U/L)', 'Vitamin D3 (ng/mL)',
    'Vitamin B12 (pg/mL)', 'TSH (uIU/mL)'
]

# 🔸 Order of meals per day used for consistent plan structure
MEAL_ORDER = [
    'Early-Morning', 'Breakfast', 'Mid-Morning Snack', 'Lunch',
    'Afternoon Snack', 'Dinner', 'Bedtime'
]

# ⭐️⭐️⭐️ NEW: BOOTSTRAP MEAL TEMPLATES ⭐️⭐️⭐️
# This defines the variety for our training data. For each meal, we list
# possible single-category templates. The script will randomly pick one.
# This teaches the AI that different types of food are valid for a given meal.
BOOTSTRAP_MEAL_TEMPLATES = {
    'Early-Morning': [
        ['Morning Drink'],
        ['Dry Fruit and Nut']
    ],
    'Breakfast': [
        ['Breakfast Dish'],
        ['Breakfast Dish'], # Higher probability for dishes
        ['Smoothie'],
        ['Paratha']
    ],
    'Mid-Morning Snack': [
        ['Fruit'],
        ['Juice'],
        ['Smoothie']
    ],
    'Lunch': [
        ['One Pot Meal'], # One pot meals are a great "theme"
        ['Dal'],          # Or the theme can be the Dal
        ['Sabzi'],        # Or the Sabzi
        ['Paratha']
    ],
    'Afternoon Snack': [
        ['Snack'],
        ['Fruit'],
        ['Dry Fruit and Nut']
    ],
    'Dinner': [
        ['One Pot Meal'],
        ['Sabzi'],
        ['Dal'],
        ['Soup']
    ],
    'Bedtime': [
        ['Night Drink']
    ]
}


# ======================================================================================
# 🔹 Main function to generate training data from raw food and health data
# ======================================================================================
def create_training_data():
    print("📦 Loading data...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    health_path = os.path.join(base_dir, "data", "health_report.xlsx")
    food_path = os.path.join(base_dir, "data", "food_items.xlsx")

    health_df = pd.read_excel(health_path)
    raw_food_df = pd.read_excel(food_path)

    print("🔄 Pre-processing Food Data...")
    raw_food_df.columns = raw_food_df.columns.str.strip()
    for col in ['Meal_Type', 'Allergens', 'Category']:
        if col in raw_food_df.columns:
            raw_food_df[col] = raw_food_df[col].fillna('Unknown')

    agg_funcs = {col: 'first' for col in raw_food_df.columns if col not in ['Food_Item', 'Meal_Type', 'Allergens', 'Category']}
    agg_funcs['Meal_Type'] = lambda x: '/'.join(x.dropna().astype(str).unique())
    agg_funcs['Allergens'] = lambda x: '/'.join(x.dropna().astype(str).unique())
    agg_funcs['Category'] = lambda x: '/'.join(x.dropna().astype(str).unique())
    food_df = raw_food_df.groupby('Food_Item').agg(agg_funcs).reset_index()

    print(f"✅ Pre-processing complete. Processed {len(food_df)} unique food items.")

    food_list = sorted(food_df['Food_Item'].unique().tolist())
    food_vocab = {food: i + 3 for i, food in enumerate(food_list)}
    food_vocab['<pad>'] = 0
    food_vocab['<sos>'] = 1
    food_vocab['<eos>'] = 2

    saved_models_dir = os.path.join(base_dir, 'saved_models')
    os.makedirs(saved_models_dir, exist_ok=True)
    vocab_path = os.path.join(saved_models_dir, 'food_vocab.json')
    with open(vocab_path, 'w') as f:
        json.dump(food_vocab, f, indent=4)
    print(f"✅ Vocabulary saved to: {vocab_path} with {len(food_vocab)} tokens")

    # ======================================================================================
    # 🔹 Generate training plans for each user
    # ======================================================================================
    training_samples = []
    print(f"\n🚀 Generating {NUM_PLANS_PER_USER} structured plans for each of the {len(health_df)} users...\n")

    for _, user_row in tqdm(health_df.iterrows(), total=len(health_df), desc="Generating plans"):
        allowed_foods_df, _ = get_allowed_foods(user_row, food_df)

        if len(allowed_foods_df) < 20:
            tqdm.write(f"⚠️ Skipping user {user_row.get('Full Name', 'N/A')} (only {len(allowed_foods_df)} allowed foods)")
            continue

        # ⭐️ Build a dictionary of allowed foods grouped by their category
        allowed_by_category = {}
        # Correctly split categories by '/'
        all_categories = set(cat.strip() for all_cats in food_df['Category'].dropna().unique() for cat in all_cats.split('/'))
        for category in all_categories:
            # Use a safer regex match to find exact category words
            cat_foods = allowed_foods_df[
                allowed_foods_df['Category'].str.contains(r'\b' + re.escape(category) + r'\b', case=False, na=False)
            ]['Food_Item'].tolist()
            if cat_foods:
                allowed_by_category[category] = cat_foods

        for _ in range(NUM_PLANS_PER_USER):
            plan_names = []
            for day_num in range(PLAN_DAYS):
                # ⭐️⭐️⭐️ REWRITTEN: Dynamic Daily Plan Generation ⭐️⭐️⭐️
                for meal_slot in MEAL_ORDER:
                    # 1. Get all possible templates for the current meal slot
                    templates = BOOTSTRAP_MEAL_TEMPLATES.get(meal_slot, [])
                    if not templates:
                        continue
                    
                    # 2. Randomly choose one template (e.g., for Lunch, it might be ['Dal'] or ['One Pot Meal'])
                    chosen_template = np.random.choice(templates)
                    
                    # 3. Gather all possible food choices from the categories in the template
                    choices = []
                    for category in chosen_template:
                        choices.extend(allowed_by_category.get(category, []))
                    
                    # 4. If no specific food is found, fall back to any allowed food
                    if not choices:
                        choices = allowed_foods_df['Food_Item'].tolist()
                    
                    # 5. If there are still no choices, skip this slot
                    if not choices:
                        continue
                        
                    # 6. Pick ONE random food to represent this meal slot and add to the plan
                    plan_names.append(np.random.choice(choices))

            if len(plan_names) != SEQUENCE_LENGTH:
                # This might happen if a user has very few allowed foods in certain categories
                # We skip these incomplete plans to ensure data quality
                continue

            plan_ids = [food_vocab[food] for food in plan_names]
            user_vector = user_row[NUMERICAL_COLS].fillna(0).values.astype(float)

            training_samples.append({
                'user_vector': list(user_vector),
                'plan_sequence': plan_ids
            })

    # ======================================================================================
    # 🔹 Save final dataset to disk
    # ======================================================================================
    training_df = pd.DataFrame(training_samples)
    training_df['user_vector'] = training_df['user_vector'].apply(json.dumps)
    training_df['plan_sequence'] = training_df['plan_sequence'].apply(json.dumps)
    data_dir = os.path.join(base_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    training_path = os.path.join(data_dir, '1_bootstrap_training_data.csv')
    training_df.to_csv(training_path, index=False)
    print(f"\n✅ All Done! Saved {len(training_df)} high-quality training samples to: {training_path}")

if __name__ == '__main__':
    create_training_data()