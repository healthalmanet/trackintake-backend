# === Required Libraries ===
import torch
import torch.nn.functional as F  # For softmax and probability sampling
import pandas as pd              # For loading Excel files
import json                      # For vocab loading
import random                    # For fallback selections
import traceback                 # For error logging
from collections import defaultdict  # For tracking food repetition
import os
from django.conf import settings
# === Custom Modules ===
from src.model import Encoder, Decoder, Seq2Seq              # Model architecture
from src.rule_engine import get_allowed_foods                # Rule engine for filtering food

# === Configuration Constants ===









SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# BASE_DIR: /home/shivam-likhar/Desktop/almanet/backend
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

MODEL_VERSION = 'v1'

VOCAB_FILE = os.path.join(SCRIPT_DIR, 'saved_models', 'food_vocab.json')
MODEL_PATH = os.path.join(SCRIPT_DIR, 'saved_models', f'diet_model_{MODEL_VERSION}_epoch_79.pth')
FOOD_DATA_FILE = os.path.join(SCRIPT_DIR, 'data', 'food_items.xlsx')
HEALTH_REPORT_FILE = os.path.join(SCRIPT_DIR, 'data', 'health_report.xlsx')
















# --- Device Selection ---
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# --- Plan Settings ---
PLAN_DAYS = 15                      # Number of days in the diet plan
MEALS_PER_DAY = 7                   # Number of meals per day
TOTAL_MEALS = PLAN_DAYS * MEALS_PER_DAY

# Meal names for formatting output
MEAL_NAMES = [
    'Early-Morning', 'Breakfast', 'Mid-Morning Snack', 'Lunch',
    'Afternoon Snack', 'Dinner', 'Bedtime'
]

# Meal type mapping used for filtering foods by appropriate slot
MEAL_TYPE_KEYWORDS = {
    'Early-Morning': 'Early-Morning',
    'Breakfast': 'Breakfast',
    'Mid-Morning Snack': 'Mid-Morning Snack',
    'Lunch': 'Lunch',
    'Afternoon Snack': 'Afternoon Snack',
    'Dinner': 'Dinner',
    'Bedtime': 'Bedtime',             # Or "Soup" etc., if you have such a type
}

# --- AI Generation Controls ---
TOP_K = 100                             # Consider top 50 tokens from model
MAX_FOOD_REPETITION_IN_PLAN = 3          # Limit food to 3 appearances per 15-day plan

# --- Model Input Dimensions (must match training config) ---
INPUT_DIM = 21
ENC_EMB_DIM = 256
DEC_EMB_DIM = 256
HID_DIM = 512

# List of numerical input features used by model
NUMERICAL_COLS = [
    'Age', 'Weight (kg)', 'Height (cm)', 'BMI (auto-calculated)', 'Waist Circumference (cm)',
    'Fasting Blood Sugar (mg/dL)', 'HbA1c (%)', 'Postprandial Sugar (mg/dL)', 'LDL (mg/dL)',
    'HDL (mg/dL)', 'Triglycerides (mg/dL)', 'CRP (mg/L)', 'ESR (mm/hr)', 'Uric Acid (mg/dL)',
    'Creatinine (mg/dL)', 'Urea (mg/dL)', 'ALT (U/L)', 'AST (U/L)', 'Vitamin D3 (ng/mL)',
    'Vitamin B12 (pg/mL)', 'TSH (uIU/mL)'
]

# === Function: Load model, vocab, and food data ===
def load_data_and_models():
    """
    Load all necessary files: model, vocab, and food data.
    Also aggregates duplicate food rows in Excel.
    """
    try:
        # --- Load vocab (food name -> index) ---
        with open(VOCAB_FILE, 'r') as f:
            food_vocab = json.load(f)
        inv_food_vocab = {v: k for k, v in food_vocab.items()}  # Reverse: index -> name
        output_dim = len(food_vocab)

        # --- Load trained Seq2Seq model ---
        encoder = Encoder(INPUT_DIM, ENC_EMB_DIM, HID_DIM)
        decoder = Decoder(output_dim, DEC_EMB_DIM, HID_DIM)
        model = Seq2Seq(encoder, decoder, DEVICE).to(DEVICE)

        checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
        model.load_state_dict(checkpoint['model_state_dict'] if 'model_state_dict' in checkpoint else checkpoint)
        model.eval()

        # --- Load and preprocess food items Excel ---
        raw_food_df = pd.read_excel(FOOD_DATA_FILE)
        raw_food_df.columns = raw_food_df.columns.str.strip()  # Clean column names

        # Group duplicates: e.g. same food listed multiple times with different values
        agg_funcs = {col: 'first' for col in raw_food_df.columns if col != 'Food_Item'}
        agg_funcs['Meal_Type'] = lambda x: '/'.join(x.unique())            # Merge meal types
        agg_funcs['Allergens'] = lambda x: '/'.join(x.dropna().unique())   # Merge allergen info

        food_df = raw_food_df.groupby('Food_Item').agg(agg_funcs).reset_index()
        food_df.set_index('Food_Item', inplace=True)  # Use food name as index for fast access

        print(f"✅ Loaded {len(food_df)} unique food items and model on {DEVICE}")
        return model, food_vocab, inv_food_vocab, food_df

    except FileNotFoundError as e:
        print(f"❌ Missing file: {e.filename}")
        return None, None, None, None
    except Exception as e:
        print("❌ Unexpected error while loading:")
        traceback.print_exc()
        return None, None, None, None

# === Function: Generate diet plan ===
# === Function: Generate diet plan ===
def generate_diet_plan(user_report, model, food_vocab, inv_food_vocab, food_df):
    """
    Generate a 15-day diet plan personalized to user input,
    using rule-based filtering and AI-guided meal generation.
    """
    # --- Step 1: Filter foods using rule engine (preferences, allergies, etc.) ---
    allowed_foods_df, suggestion_flags = get_allowed_foods(user_report, food_df.reset_index())

    print(f"\n🍽️  Generating diet plan for: {user_report['Full Name']}")
    print("\n📋 List of Allowed Foods (after filtering):")
    print("=" * 40)
    for i, row in allowed_foods_df.iterrows():
     print(f"{i+1}. {row['Food_Item']} | Meal Types: {row['Meal_Type']}")
    print(f"\n✅ Total allowed: {len(allowed_foods_df)} items\n")

    allowed_food_names = set(allowed_foods_df['Food_Item'])

    if len(allowed_food_names) < 15:
        return f"❗ Not enough safe foods found (only {len(allowed_food_names)}). Aborting."

    # --- Step 2: Encode user features into tensor ---
    # Fix for FutureWarning
    full_user_report = user_report.reindex(NUMERICAL_COLS).fillna(0)
    user_vector = torch.tensor(full_user_report.values, dtype=torch.float32).unsqueeze(0).to(DEVICE)

    # --- Step 3: AI-guided plan generation with rule enforcement ---
    final_plan_ids = []
    plan_usage_count = defaultdict(int)  # Tracks how often each food is used

    with torch.no_grad():
        hidden, cell = model.encoder(user_vector)
        input_token = torch.tensor([food_vocab['<sos>']], device=DEVICE)

        for day in range(PLAN_DAYS):
            daily_used_ids = set()  # To prevent repeat on same day

            for meal_name in MEAL_NAMES:
                output, hidden, cell = model.decoder(input_token, hidden, cell)

                probs = F.softmax(output, dim=-1)
                
                # --- Find best candidate from Top-K predictions ---
                top_k_probs, top_k_indices = torch.topk(probs, TOP_K)
                valid_candidates = []
                for i in range(TOP_K):
                    candidate_id = top_k_indices[0, i].item()
                    candidate_name = inv_food_vocab.get(candidate_id)

                    if not candidate_name or candidate_name not in allowed_food_names:
                        continue
                    if candidate_id in daily_used_ids:
                        continue
                    if plan_usage_count[candidate_id] >= MAX_FOOD_REPETITION_IN_PLAN:
                        continue

                    meal_keyword = MEAL_TYPE_KEYWORDS[meal_name]
                    food_types = food_df.loc[candidate_name, 'Meal_Type']
                    if meal_keyword.lower() not in food_types.lower():
                        # A small allowance for 'main course' in your original logic
                        if meal_keyword in ['Lunch', 'Dinner'] and 'main course' in food_types.lower():
                            pass
                        else:
                            continue
                    
                    valid_candidates.append((candidate_id, top_k_probs[0, i].item()))
                
                # --- Choose final token ---
                next_token_id = None # Initialize to None

                if valid_candidates:
                    ids, weights = zip(*valid_candidates)
                    weights_tensor = torch.tensor(weights, dtype=torch.float32)
                    next_token_id = ids[torch.multinomial(weights_tensor / weights_tensor.sum(), 1).item()]
                else:
                    # --- NEW, SMARTER FALLBACK ---
                    # Fallback Step 1: Search ALL model predictions if Top-K fails
                    all_probs, all_indices = torch.topk(probs, len(food_vocab))
                    
                    for i in range(len(food_vocab)):
                        candidate_id = all_indices[0, i].item()
                        candidate_name = inv_food_vocab.get(candidate_id)

                        # Check all the same rules again
                        if not candidate_name or candidate_name not in allowed_food_names: continue
                        if candidate_id in daily_used_ids: continue
                        if plan_usage_count[candidate_id] >= MAX_FOOD_REPETITION_IN_PLAN: continue
                        
                        meal_keyword = MEAL_TYPE_KEYWORDS[meal_name]
                        food_types = food_df.loc[candidate_name, 'Meal_Type']
                        if meal_keyword.lower() not in food_types.lower(): continue

                        # Found the highest-ranking valid food outside of TOP_K!
                        next_token_id = candidate_id
                        break # Stop searching
                    
                    # --- ORIGINAL, LAST-RESORT FALLBACK ---
                    if next_token_id is None:
                        # Only use this if the model truly predicts ZERO valid foods.
                        fallback_pool = allowed_foods_df[
                            (~allowed_foods_df['Food_Item'].isin({inv_food_vocab.get(i) for i in daily_used_ids})) &
                            (allowed_foods_df['Meal_Type'].str.contains(meal_keyword, case=False, na=False)) &
                            (allowed_foods_df['Food_Item'].apply(lambda x: plan_usage_count.get(food_vocab.get(x, -1), 0) < MAX_FOOD_REPETITION_IN_PLAN))
                        ]
                        if fallback_pool.empty:
                            # If still empty, relax the repetition constraint for the fallback
                             fallback_pool = allowed_foods_df[
                                (~allowed_foods_df['Food_Item'].isin({inv_food_vocab.get(i) for i in daily_used_ids})) &
                                (allowed_foods_df['Meal_Type'].str.contains(meal_keyword, case=False, na=False))
                            ]
                        
                        if fallback_pool.empty:
                            # If STILL empty (e.g., no foods for 'Bedtime'), just pick any allowed food
                            fallback_pool = allowed_foods_df
                        
                        fallback_name = fallback_pool.sample(1)['Food_Item'].iloc[0]
                        next_token_id = food_vocab[fallback_name]

                # --- Update state trackers (THIS MUST BE AT THIS INDENTATION LEVEL) ---
                final_plan_ids.append(next_token_id)
                daily_used_ids.add(next_token_id)
                plan_usage_count[next_token_id] += 1
                input_token = torch.tensor([next_token_id], device=DEVICE)

    # --- Step 4: Format plan text output for nutritionist ---
    # (The rest of your function is fine)
    print("📝 Formatting diet plan...")
    plan_lines = []
    plan_lines.append(f"--- AI-GENERATED DIET PLAN (v{MODEL_VERSION}) ---")
    plan_lines.append(f"Patient: {user_report['Full Name']}\n")
    plan_lines.append("Note: This plan follows medical rules and AI variety control.\n")

    for day in range(PLAN_DAYS):
        plan_lines.append(f"--- Day {day + 1} ---")
        for i, meal_name in enumerate(MEAL_NAMES):
            idx = day * MEALS_PER_DAY + i
            if idx < len(final_plan_ids):
                food_id = final_plan_ids[idx]
                food_name = inv_food_vocab.get(food_id, 'Unknown Food')
                plan_lines.append(f"{meal_name}: {food_name}")
        plan_lines.append("")  # Empty line between days

    return "\n".join(plan_lines)
# === MAIN: Generate Sample Plan ===
if __name__ == '__main__':
    # Load all assets
    model, food_vocab, inv_food_vocab, food_df = load_data_and_models()

    if model:
        try:
            # Sample user profile (you can replace this with one from Excel)
            sample_user_data = {
                "Full Name": "Healthy Profile User",
                "Age": 30,
                "Weight (kg)": 70,
                "Height (cm)": 175,
                "BMI (auto-calculated)": 22.9,
                "Waist Circumference (cm)": 85,
                "Gender": "Male",
                "Activity Level": "Moderately Active",
                "Dietary Preference": "Vegetarian",
                "Known Allergies": "None",
                "Diabetic (Yes/No)": "No",
                "Hypertension (Yes/No)": "No",
                "Heart condition (CVD) (Yes/No)": "No",
                "Thyroid disorder (Yes/No)": "No",
                "Arthritis (RA/OA/Gout) (Yes/No)": "No",
                "Gastric issues (IBS/GERD) (Yes/No)": "No",
                "Any other chronic condition": "",
                "Family history of diseases": ""
            }

            sample_user = pd.Series(sample_user_data)
            
            # health_reports = pd.read_excel(HEALTH_REPORT_FILE)
            # sample_user = health_reports.iloc[1] 
            
            final_plan = generate_diet_plan(sample_user, model, food_vocab, inv_food_vocab, food_df)

            # Display & save output
            print("\n" + "=" * 60)
            print("✅ FINAL GENERATED PLAN")
            print("=" * 60)
            print(final_plan)

            # Save to .txt
            file_name = f"generated_plan_{sample_user['Full Name'].replace(' ', '_')}.txt"
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(final_plan)
            print(f"\n💾 Plan saved to: {file_name}")

        except Exception as e:
            print(f"❌ Error during plan generation: {e}")
            traceback.print_exc()

