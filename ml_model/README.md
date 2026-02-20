# AI Diet Recommendation System with Human-in-the-Loop Feedback

This project implements a hybrid AI system to generate personalized 15-day diet plans based on user health reports. The final plans are intended for review and approval by a professional nutritionist.

## Core Architecture

1.  **Rule-Based Engine (Safety Net):** A set of strict rules (`src/rule_engine.py`) analyzes a user's health conditions and allergies to create a "Safe Foods List". This ensures no medically inappropriate food is ever recommended.

2.  **AI Seq2Seq Model (The Creative Chef):** A sequence-to-sequence machine learning model (`src/model.py`) learns the patterns of creating varied and logical meal plans. It is trained to map a user's health profile to a 15-day sequence of meals.

3.  **Human-in-the-Loop (The Virtuous Cycle):** The AI-generated plan is a DRAFT. A nutritionist reviews and modifies it. This expert-approved final plan is the most valuable data we have. It's saved and used to retrain and improve the AI model over time, making future drafts better.

## How to Run the System

**Prerequisites:**
- Python 3.8+
- Install required libraries: `pip install pandas openpyxl torch tqdm`
- Place your `health_report.xlsx` and `food_items.xlsx` in the `data/` directory.

### Step-by-Step Workflow

1.  **Prepare Initial Training Data (Run Once):**
    This script uses the rule engine to create a large, safe dataset to train our first model.
    ```bash
    python 1_prepare_bootstrap_data.py
    ```

2.  **Train the V1 Model (Run Once):**
    This trains the AI on the initial dataset.
    ```bash
    python 2_train_initial_model.py
    ```

3.  **Generate a Plan for Nutritionist Review (Use in Production):**
    This script takes a user report, generates a draft plan, and formats it for review.
    ```bash
    python 3_generate_plan_for_review.py
    ```
    Your application's backend will call the functions in this script.

4.  **Retrain with Expert Feedback (Run Periodically):**
    After your app has collected a number of nutritionist-approved plans in `data/approved_plans.csv`, run this script to create a smarter V2 model.
    ```bash
    python 4_retrain_with_feedback.py
    ```