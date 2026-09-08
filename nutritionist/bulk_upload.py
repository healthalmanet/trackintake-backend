import io
import re
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from user.models import User
from userProfile.models import UserProfile, LabReport
from nutritionist.models import PatientAssignment


# ==============================================================================
# Column Definitions & Schemas
# ==============================================================================

TEMPLATE_COLUMNS = [
    # Basic User Info (Required)
    {"key": "full_name", "header": "Full Name *", "required": True, "category": "user", "type": "str", "help": "Patient's full legal or preferred name"},
    {"key": "email", "header": "Email *", "required": True, "category": "user", "type": "email", "help": "Unique email address for account & communication"},
    {"key": "password", "header": "Password (Optional)", "required": False, "category": "user", "type": "str", "help": "Account password (defaults to Default@123 if blank)"},
    {"key": "mobile_number", "header": "Mobile Number", "required": False, "category": "profile", "type": "str", "help": "Phone number with country code if applicable"},
    
    # Profile & Demographics
    {"key": "date_of_birth", "header": "Date of Birth (YYYY-MM-DD)", "required": False, "category": "profile", "type": "date", "help": "Format: YYYY-MM-DD, e.g. 1990-05-15"},
    {"key": "gender", "header": "Gender (male/female/other)", "required": False, "category": "profile", "type": "choice", "choices": ["male", "female", "other"], "help": "male, female, or other"},
    {"key": "country", "header": "Country", "required": False, "category": "profile", "type": "str", "help": "Country of residence"},
    {"key": "city", "header": "City", "required": False, "category": "profile", "type": "str", "help": "City of residence"},
    {"key": "occupation", "header": "Occupation", "required": False, "category": "profile", "type": "str", "help": "e.g. Software Engineer, Teacher, Doctor"},
    
    # Body Metrics & Lifestyle
    {"key": "height_cm", "header": "Height (cm)", "required": False, "category": "profile", "type": "float", "help": "Height in centimeters, e.g. 172.5"},
    {"key": "weight_kg", "header": "Weight (kg)", "required": False, "category": "profile", "type": "float", "help": "Weight in kilograms, e.g. 74.0"},
    {"key": "activity_level", "header": "Activity Level", "required": False, "category": "profile", "type": "choice", 
     "choices": ["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"],
     "help": "sedentary / lightly_active / moderately_active / very_active / extra_active"},
    {"key": "goal", "header": "Primary Goal", "required": False, "category": "profile", "type": "choice",
     "choices": ["lose_weight", "maintain", "gain_weight"],
     "help": "lose_weight / maintain / gain_weight"},
    {"key": "diet_type", "header": "Diet Type", "required": False, "category": "profile", "type": "choice",
     "choices": ["vegetarian", "non_vegetarian", "vegan", "eggetarian", "keto", "other"],
     "help": "vegetarian / non_vegetarian / vegan / eggetarian / keto / other"},
    {"key": "allergies", "header": "Allergies (comma-separated)", "required": False, "category": "profile", "type": "str", "help": "e.g. Peanuts, Lactose, Shellfish"},
    
    # Medical History (Yes / No)
    {"key": "is_diabetic", "header": "Diabetic? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},
    {"key": "is_hypertensive", "header": "Hypertensive? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},
    {"key": "has_heart_condition", "header": "Heart Condition? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},
    {"key": "has_thyroid_disorder", "header": "Thyroid Disorder? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},
    {"key": "has_arthritis", "header": "Arthritis? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},
    {"key": "has_gastric_issues", "header": "Gastric Issues? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},
    {"key": "other_chronic_condition", "header": "Other Chronic Conditions", "required": False, "category": "profile", "type": "str", "help": "e.g. Migraine, Asthma"},
    {"key": "family_history", "header": "Family Medical History", "required": False, "category": "profile", "type": "str", "help": "e.g. Mother has Type 2 Diabetes"},
    {"key": "is_pregnant", "header": "Pregnant? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No (Females only)"},
    {"key": "due_date", "header": "Due Date (YYYY-MM-DD)", "required": False, "category": "profile", "type": "date", "help": "If pregnant (YYYY-MM-DD)"},
    {"key": "is_breastfeeding", "header": "Breastfeeding? (Yes/No)", "required": False, "category": "profile", "type": "bool", "help": "Yes or No"},

    # Initial Lab Report (Optional)
    {"key": "lab_report_date", "header": "Lab Report Date (YYYY-MM-DD)", "required": False, "category": "lab", "type": "date", "help": "Date of the lab report"},
    {"key": "fasting_blood_sugar", "header": "Fasting Sugar (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 95.0"},
    {"key": "postprandial_sugar", "header": "Postprandial Sugar (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 135.0"},
    {"key": "hba1c", "header": "HbA1c (%)", "required": False, "category": "lab", "type": "float", "help": "e.g. 5.6"},
    {"key": "blood_pressure_systolic", "header": "BP Systolic (mmHg)", "required": False, "category": "lab", "type": "int", "help": "e.g. 120"},
    {"key": "blood_pressure_diastolic", "header": "BP Diastolic (mmHg)", "required": False, "category": "lab", "type": "int", "help": "e.g. 80"},
    {"key": "ldl_cholesterol", "header": "LDL Cholesterol (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 110.0"},
    {"key": "hdl_cholesterol", "header": "HDL Cholesterol (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 52.0"},
    {"key": "triglycerides", "header": "Triglycerides (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 145.0"},
    {"key": "tsh", "header": "TSH (µIU/mL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 2.4"},
    {"key": "vitamin_d3", "header": "Vitamin D3 (ng/mL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 28.5"},
    {"key": "vitamin_b12", "header": "Vitamin B12 (pg/mL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 380.0"},
    {"key": "uric_acid", "header": "Uric Acid (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 5.2"},
    {"key": "creatinine", "header": "Creatinine (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 0.9"},
    {"key": "urea", "header": "Urea (mg/dL)", "required": False, "category": "lab", "type": "float", "help": "e.g. 28.0"},
    {"key": "alt", "header": "ALT / SGPT (U/L)", "required": False, "category": "lab", "type": "float", "help": "e.g. 24.0"},
    {"key": "ast", "header": "AST / SGOT (U/L)", "required": False, "category": "lab", "type": "float", "help": "e.g. 22.0"},
]

SAMPLE_PATIENTS_10 = [
    {
        "full_name": "Aarav Sharma", "email": "aarav.sharma.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 98765 43210",
        "date_of_birth": "1988-04-12", "gender": "male", "country": "India", "city": "Mumbai", "occupation": "Software Architect",
        "height_cm": 178, "weight_kg": 86, "activity_level": "sedentary", "goal": "lose_weight", "diet_type": "vegetarian",
        "allergies": "Peanuts", "is_diabetic": "No", "is_hypertensive": "Yes", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "Yes", "other_chronic_condition": "Mild GERD", "family_history": "Father has Type 2 Diabetes",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-08-15", "fasting_blood_sugar": 105, "postprandial_sugar": 142, "hba1c": 5.8,
        "blood_pressure_systolic": 135, "blood_pressure_diastolic": 88, "ldl_cholesterol": 138, "hdl_cholesterol": 44,
        "triglycerides": 180, "tsh": 2.1, "vitamin_d3": 19.5, "vitamin_b12": 290, "uric_acid": 6.8, "creatinine": 1.0, "urea": 32, "alt": 35, "ast": 28
    },
    {
        "full_name": "Pooja Patel", "email": "pooja.patel.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 98234 56789",
        "date_of_birth": "1994-09-22", "gender": "female", "country": "India", "city": "Ahmedabad", "occupation": "Graphic Designer",
        "height_cm": 162, "weight_kg": 54, "activity_level": "moderately_active", "goal": "maintain", "diet_type": "vegan",
        "allergies": "Soy, Lactose", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "Yes",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "Hypothyroidism", "family_history": "None",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-07-20", "fasting_blood_sugar": 88, "postprandial_sugar": 115, "hba1c": 5.2,
        "blood_pressure_systolic": 115, "blood_pressure_diastolic": 75, "ldl_cholesterol": 95, "hdl_cholesterol": 58,
        "triglycerides": 110, "tsh": 4.8, "vitamin_d3": 22.0, "vitamin_b12": 240, "uric_acid": 4.1, "creatinine": 0.7, "urea": 22, "alt": 18, "ast": 20
    },
    {
        "full_name": "Rohan Gupta", "email": "rohan.gupta.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 97112 34567",
        "date_of_birth": "1997-11-05", "gender": "male", "country": "India", "city": "Delhi", "occupation": "Fitness Trainer",
        "height_cm": 183, "weight_kg": 75, "activity_level": "very_active", "goal": "gain_weight", "diet_type": "non_vegetarian",
        "allergies": "", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "", "family_history": "",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-08-01", "fasting_blood_sugar": 82, "postprandial_sugar": 102, "hba1c": 4.9,
        "blood_pressure_systolic": 118, "blood_pressure_diastolic": 76, "ldl_cholesterol": 85, "hdl_cholesterol": 62,
        "triglycerides": 92, "tsh": 1.8, "vitamin_d3": 38.0, "vitamin_b12": 520, "uric_acid": 5.5, "creatinine": 0.9, "urea": 26, "alt": 21, "ast": 22
    },
    {
        "full_name": "Ananya Mukherjee", "email": "ananya.m.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 99345 67890",
        "date_of_birth": "1992-02-18", "gender": "female", "country": "India", "city": "Kolkata", "occupation": "College Professor",
        "height_cm": 158, "weight_kg": 68, "activity_level": "lightly_active", "goal": "lose_weight", "diet_type": "non_vegetarian",
        "allergies": "Eggplant", "is_diabetic": "Yes", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "Type 2 Diabetes (Managed)", "family_history": "Maternal grandfather had CVD",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-08-10", "fasting_blood_sugar": 140, "postprandial_sugar": 185, "hba1c": 7.4,
        "blood_pressure_systolic": 125, "blood_pressure_diastolic": 82, "ldl_cholesterol": 125, "hdl_cholesterol": 48,
        "triglycerides": 165, "tsh": 2.5, "vitamin_d3": 16.0, "vitamin_b12": 310, "uric_acid": 5.0, "creatinine": 0.8, "urea": 25, "alt": 29, "ast": 25
    },
    {
        "full_name": "Vikram Rathore", "email": "vikram.rathore.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 98989 12345",
        "date_of_birth": "1975-06-30", "gender": "male", "country": "India", "city": "Jaipur", "occupation": "Hotelier",
        "height_cm": 175, "weight_kg": 92, "activity_level": "sedentary", "goal": "lose_weight", "diet_type": "eggetarian",
        "allergies": "", "is_diabetic": "Yes", "is_hypertensive": "Yes", "has_heart_condition": "Yes", "has_thyroid_disorder": "No",
        "has_arthritis": "Yes", "has_gastric_issues": "Yes", "other_chronic_condition": "Osteoarthritis knee", "family_history": "Father had early heart attack",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-08-25", "fasting_blood_sugar": 155, "postprandial_sugar": 210, "hba1c": 8.1,
        "blood_pressure_systolic": 145, "blood_pressure_diastolic": 92, "ldl_cholesterol": 160, "hdl_cholesterol": 38,
        "triglycerides": 220, "tsh": 3.0, "vitamin_d3": 14.0, "vitamin_b12": 260, "uric_acid": 7.8, "creatinine": 1.2, "urea": 42, "alt": 48, "ast": 40
    },
    {
        "full_name": "Sneha Iyer", "email": "sneha.iyer.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 97456 12389",
        "date_of_birth": "1996-08-14", "gender": "female", "country": "India", "city": "Chennai", "occupation": "Financial Analyst",
        "height_cm": 165, "weight_kg": 62, "activity_level": "moderately_active", "goal": "maintain", "diet_type": "vegetarian",
        "allergies": "Tree nuts", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "", "family_history": "Hypertension in parents",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-07-15", "fasting_blood_sugar": 90, "postprandial_sugar": 118, "hba1c": 5.1,
        "blood_pressure_systolic": 110, "blood_pressure_diastolic": 72, "ldl_cholesterol": 102, "hdl_cholesterol": 55,
        "triglycerides": 115, "tsh": 1.9, "vitamin_d3": 31.0, "vitamin_b12": 450, "uric_acid": 4.2, "creatinine": 0.8, "urea": 20, "alt": 19, "ast": 18
    },
    {
        "full_name": "David Fernandes", "email": "david.f.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 98123 45670",
        "date_of_birth": "1985-12-03", "gender": "male", "country": "India", "city": "Goa", "occupation": "Chef",
        "height_cm": 170, "weight_kg": 78, "activity_level": "very_active", "goal": "lose_weight", "diet_type": "keto",
        "allergies": "Shellfish", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "", "family_history": "None",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-08-05", "fasting_blood_sugar": 92, "postprandial_sugar": 110, "hba1c": 5.3,
        "blood_pressure_systolic": 122, "blood_pressure_diastolic": 78, "ldl_cholesterol": 112, "hdl_cholesterol": 50,
        "triglycerides": 130, "tsh": 2.0, "vitamin_d3": 34.0, "vitamin_b12": 490, "uric_acid": 5.8, "creatinine": 0.9, "urea": 28, "alt": 25, "ast": 24
    },
    {
        "full_name": "Meera Nambiar", "email": "meera.nambiar.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 96543 21890",
        "date_of_birth": "1998-05-20", "gender": "female", "country": "India", "city": "Kochi", "occupation": "Content Creator",
        "height_cm": 160, "weight_kg": 50, "activity_level": "lightly_active", "goal": "gain_weight", "diet_type": "non_vegetarian",
        "allergies": "", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "", "family_history": "",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-06-28", "fasting_blood_sugar": 85, "postprandial_sugar": 112, "hba1c": 5.0,
        "blood_pressure_systolic": 112, "blood_pressure_diastolic": 70, "ldl_cholesterol": 90, "hdl_cholesterol": 60,
        "triglycerides": 95, "tsh": 1.7, "vitamin_d3": 29.0, "vitamin_b12": 420, "uric_acid": 3.9, "creatinine": 0.7, "urea": 21, "alt": 16, "ast": 17
    },
    {
        "full_name": "Karan Singhania", "email": "karan.s.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 99887 76655",
        "date_of_birth": "1980-10-10", "gender": "male", "country": "India", "city": "Bengaluru", "occupation": "Entrepreneur",
        "height_cm": 180, "weight_kg": 88, "activity_level": "extra_active", "goal": "maintain", "diet_type": "non_vegetarian",
        "allergies": "Dust, Pollen", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "No", "other_chronic_condition": "", "family_history": "Diabetes in paternal uncle",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-08-18", "fasting_blood_sugar": 96, "postprandial_sugar": 128, "hba1c": 5.4,
        "blood_pressure_systolic": 120, "blood_pressure_diastolic": 80, "ldl_cholesterol": 115, "hdl_cholesterol": 52,
        "triglycerides": 140, "tsh": 2.2, "vitamin_d3": 35.0, "vitamin_b12": 510, "uric_acid": 5.6, "creatinine": 1.0, "urea": 30, "alt": 28, "ast": 26
    },
    {
        "full_name": "Divya Chawla", "email": "divya.chawla.sample@trackintake.com", "password": "Default@123", "mobile_number": "+91 98711 22334",
        "date_of_birth": "1993-03-25", "gender": "female", "country": "India", "city": "Chandigarh", "occupation": "HR Manager",
        "height_cm": 167, "weight_kg": 64, "activity_level": "moderately_active", "goal": "lose_weight", "diet_type": "vegetarian",
        "allergies": "Gluten (Mild)", "is_diabetic": "No", "is_hypertensive": "No", "has_heart_condition": "No", "has_thyroid_disorder": "No",
        "has_arthritis": "No", "has_gastric_issues": "Yes", "other_chronic_condition": "IBS", "family_history": "Hypothyroidism in mother",
        "is_pregnant": "No", "due_date": "", "is_breastfeeding": "No",
        "lab_report_date": "2026-07-30", "fasting_blood_sugar": 91, "postprandial_sugar": 120, "hba1c": 5.2,
        "blood_pressure_systolic": 116, "blood_pressure_diastolic": 74, "ldl_cholesterol": 98, "hdl_cholesterol": 56,
        "triglycerides": 105, "tsh": 2.8, "vitamin_d3": 25.0, "vitamin_b12": 370, "uric_acid": 4.5, "creatinine": 0.8, "urea": 24, "alt": 20, "ast": 19
    },
]


# ==============================================================================
# Excel Template Generator
# ==============================================================================

def generate_patient_template_excel():
    """
    Generates a beautifully formatted Excel workbook with:
    1. 'Patient Data' worksheet containing pre-filled column headers and 10 realistic example rows.
    2. 'Instructions & Guide' worksheet explaining all fields, formats, and choices.
    """
    wb = openpyxl.Workbook()

    # --- Sheet 1: Patients Template ---
    ws = wb.active
    ws.title = "Patient Data"
    ws.views.sheetView[0].showGridLines = True

    # Palette
    req_fill = PatternFill(start_color="1B5E20", end_color="1B5E20", fill_type="solid")     # Dark Emerald Green
    opt_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")     # Medium Forest Green
    lab_fill = PatternFill(start_color="00695C", end_color="00695C", fill_type="solid")     # Teal for Lab Report
    sample_fill_even = PatternFill(start_color="F1F8E9", end_color="F1F8E9", fill_type="solid") # Light mint
    sample_fill_odd = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10, color="212121")
    note_font = Font(name="Calibri", size=9, italic=True, color="616161")

    thin_border = Border(
        left=Side(style='thin', color='E0E0E0'),
        right=Side(style='thin', color='E0E0E0'),
        top=Side(style='thin', color='E0E0E0'),
        bottom=Side(style='thin', color='E0E0E0')
    )

    # Row 1: Group / Category Banner
    # Row 2: Column Headers
    headers = [col["header"] for col in TEMPLATE_COLUMNS]

    for col_idx, col_def in enumerate(TEMPLATE_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_def["header"])
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        if col_def["required"]:
            cell.fill = req_fill
        elif col_def["category"] == "lab":
            cell.fill = lab_fill
        else:
            cell.fill = opt_fill

    ws.row_dimensions[1].height = 36

    # Insert 10 Sample Rows
    for row_idx, sample_data in enumerate(SAMPLE_PATIENTS_10, start=2):
        row_fill = sample_fill_even if row_idx % 2 == 0 else sample_fill_odd
        for col_idx, col_def in enumerate(TEMPLATE_COLUMNS, 1):
            val = sample_data.get(col_def["key"], "")
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = row_fill
            cell.border = thin_border
            cell.alignment = Alignment(
                horizontal="center" if col_def["type"] in ["choice", "bool", "date", "int", "float"] else "left",
                vertical="center"
            )
        ws.row_dimensions[row_idx].height = 22

    # Auto-fit column widths
    for col_idx, col_def in enumerate(TEMPLATE_COLUMNS, 1):
        col_letter = get_column_letter(col_idx)
        header_len = len(col_def["header"])
        ws.column_dimensions[col_letter].width = max(header_len + 4, 18)

    # Freeze header row
    ws.freeze_panes = "A2"

    # --- Sheet 2: Field Reference Guide ---
    guide_ws = wb.create_sheet(title="Field Guide & Instructions")
    guide_ws.views.sheetView[0].showGridLines = True

    guide_title_fill = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
    guide_header_fill = PatternFill(start_color="303F9F", end_color="303F9F", fill_type="solid")

    guide_ws.cell(row=1, column=1, value="TrackIntake - Bulk Patient Import Guide").font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    guide_ws.cell(row=1, column=1).fill = guide_title_fill
    guide_ws.merge_cells("A1:E1")
    guide_ws.row_dimensions[1].height = 30

    guide_headers = ["Field / Column Name", "Required?", "Accepted Values / Format", "Description", "Example"]
    for col_idx, h in enumerate(guide_headers, 1):
        cell = guide_ws.cell(row=3, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = guide_header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    guide_ws.row_dimensions[3].height = 26

    guide_rows = [
        ("Full Name *", "YES (Mandatory)", "Text (e.g. John Doe)", "Patient's full name", "Aarav Sharma"),
        ("Email *", "YES (Mandatory)", "Valid unique email address", "Email used for account login & notifications", "aarav@example.com"),
        ("Password (Optional)", "Optional", "Text", "Initial password (defaults to Default@123 if left empty)", "Default@123"),
        ("Mobile Number", "Optional", "Phone number string", "Contact phone number", "+91 9876543210"),
        ("Date of Birth", "Optional", "YYYY-MM-DD or DD/MM/YYYY", "Patient's birth date", "1990-05-15"),
        ("Gender", "Optional", "male / female / other", "Gender of the patient", "male"),
        ("Country", "Optional", "Text", "Country of residence", "India"),
        ("City", "Optional", "Text", "City of residence", "Mumbai"),
        ("Occupation", "Optional", "Text", "Job or profession", "Software Engineer"),
        ("Height (cm)", "Optional", "Number (cm)", "Current height in centimeters", "175.5"),
        ("Weight (kg)", "Optional", "Number (kg)", "Current weight in kilograms", "72.0"),
        ("Activity Level", "Optional", "sedentary / lightly_active / moderately_active / very_active / extra_active", "Daily physical activity level", "moderately_active"),
        ("Primary Goal", "Optional", "lose_weight / maintain / gain_weight", "Primary fitness or health objective", "lose_weight"),
        ("Diet Type", "Optional", "vegetarian / non_vegetarian / vegan / eggetarian / keto / other", "Dietary lifestyle preference", "vegetarian"),
        ("Allergies", "Optional", "Comma-separated text", "List of food allergies", "Peanuts, Shellfish"),
        ("Diabetic / Hypertensive / Heart Condition / Thyroid / Arthritis / Gastric", "Optional", "Yes / No or True / False", "Known medical conditions (flags for AI meal planner)", "Yes or No"),
        ("Pregnant / Breastfeeding", "Optional", "Yes / No", "Pregnancy / postpartum status (Females only)", "No"),
        ("Due Date", "Optional", "YYYY-MM-DD", "Estimated due date if pregnant", "2026-12-15"),
        ("Lab Report Fields", "Optional", "Numeric measurements", "Initial lab biomarkers (fasting sugar, HbA1c, lipids, vitamins, etc.)", "Fasting: 95, HbA1c: 5.6"),
    ]

    for row_idx, r in enumerate(guide_rows, start=4):
        bg = sample_fill_even if row_idx % 2 == 0 else sample_fill_odd
        for col_idx, val in enumerate(r, 1):
            cell = guide_ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = bg
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        guide_ws.row_dimensions[row_idx].height = 24

    guide_ws.column_dimensions["A"].width = 28
    guide_ws.column_dimensions["B"].width = 18
    guide_ws.column_dimensions["C"].width = 40
    guide_ws.column_dimensions["D"].width = 45
    guide_ws.column_dimensions["E"].width = 25

    # Instructions box at bottom
    inst_start_row = len(guide_rows) + 6
    guide_ws.cell(row=inst_start_row, column=1, value="How to Use This Template:").font = Font(name="Calibri", size=12, bold=True, color="1B5E20")
    instructions = [
        "1. Open the 'Patient Data' tab.",
        "2. Review the 10 sample rows to see valid formats and values.",
        "3. Delete or replace the 10 sample rows with your actual patient records (up to 1,000+ at once).",
        "4. 'Full Name *' and 'Email *' are strictly mandatory for every row.",
        "5. Save as .xlsx and upload via the 'Bulk Upload (.xlsx)' option in the Add New Patient dialog.",
        "6. All created patients will be immediately assigned to your nutritionist account.",
    ]
    for i, inst in enumerate(instructions):
        guide_ws.cell(row=inst_start_row + 1 + i, column=1, value=inst).font = data_font

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ==============================================================================
# Helper Parsers for Bulk Upload
# ==============================================================================

def normalize_header(header_str):
    """
    Normalizes header string (e.g. 'Full Name *' -> 'full_name', 'Date of Birth (YYYY-MM-DD)' -> 'date_of_birth')
    """
    if not header_str:
        return ""
    h = str(header_str).strip().lower()
    # Remove contents inside parentheses like (YYYY-MM-DD) or (Yes/No)
    h = re.sub(r'\(.*?\)', '', h)
    # Remove asterisks and special characters
    h = re.sub(r'[^a-z0-9]+', '_', h)
    return h.strip('_')


def parse_date_value(val):
    if val is None or str(val).strip() == "":
        return None
    if isinstance(val, (datetime, date)):
        if isinstance(val, datetime):
            return val.date()
        return val
    
    val_str = str(val).strip()
    date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    for fmt in date_formats:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None


def parse_bool_value(val):
    if val is None or str(val).strip() == "":
        return False
    val_str = str(val).strip().lower()
    return val_str in ["yes", "y", "true", "1", "t"]


def parse_float_value(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def parse_int_value(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def clean_choice_key(val):
    """
    Strips leading/trailing whitespace, converts to lowercase,
    and collapses any sequence of spaces, hyphens, or underscores to single underscore.
    Example: '  Non - Vegetarian  ' -> 'non_vegetarian'
    """
    if not val:
        return ""
    v = str(val).strip().lower()
    return re.sub(r'[\s\-_]+', '_', v)


# Map common variations of choice strings to model valid choices
GENDER_MAP = {
    "male": "male", "m": "male", "man": "male", "boy": "male",
    "female": "female", "f": "female", "woman": "female", "girl": "female",
    "other": "other", "non_binary": "other", "nonbinary": "other"
}

ACTIVITY_MAP = {
    "sedentary": "sedentary", "sedentary_little_or_no_exercise": "sedentary",
    "lightly_active": "lightly_active", "light": "lightly_active", "lightly_active_light_exercise_sports_1_3_days_week": "lightly_active",
    "moderately_active": "moderately_active", "moderate": "moderately_active", "moderately_active_moderate_exercise_sports_3_5_days_week": "moderately_active",
    "very_active": "very_active", "hard": "very_active", "very_active_hard_exercise_sports_6_7_days_a_week": "very_active",
    "extra_active": "extra_active", "extra": "extra_active", "extra_active_very_hard_exercise_physical_job": "extra_active"
}

GOAL_MAP = {
    "lose_weight": "lose_weight", "lose": "lose_weight", "weight_loss": "lose_weight", "fat_loss": "lose_weight",
    "maintain": "maintain", "maintain_weight": "maintain", "maintenance": "maintain",
    "gain_weight": "gain_weight", "gain": "gain_weight", "weight_gain": "gain_weight", "muscle_gain": "gain_weight"
}

DIET_MAP = {
    "vegetarian": "vegetarian", "veg": "vegetarian",
    "non_vegetarian": "non_vegetarian", "non_veg": "non_vegetarian", "nonveg": "non_vegetarian",
    "vegan": "vegan",
    "eggetarian": "eggetarian", "egg": "eggetarian",
    "keto": "keto", "ketogenic": "keto",
    "other": "other"
}


# Header match lookup dictionary
HEADER_TO_KEY = {}
for col in TEMPLATE_COLUMNS:
    norm = normalize_header(col["header"])
    HEADER_TO_KEY[norm] = col["key"]
    # Also map direct key
    HEADER_TO_KEY[col["key"]] = col["key"]

# Extra custom aliases
HEADER_TO_KEY.update({
    "name": "full_name",
    "patient_name": "full_name",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "phone": "mobile_number",
    "phone_number": "mobile_number",
    "mobile": "mobile_number",
    "height": "height_cm",
    "weight": "weight_kg",
    "activity": "activity_level",
    "diet": "diet_type",
    "diabetes": "is_diabetic",
    "diabetic": "is_diabetic",
    "hypertension": "is_hypertensive",
    "hypertensive": "is_hypertensive",
    "bp": "blood_pressure_systolic",
    "bp_systolic": "blood_pressure_systolic",
    "bp_diastolic": "blood_pressure_diastolic",
    "fasting_sugar": "fasting_blood_sugar",
    "post_prandial_sugar": "postprandial_sugar",
    "pp_sugar": "postprandial_sugar",
    "lab_date": "lab_report_date",
    "report_date": "lab_report_date",
})


# ==============================================================================
# Bulk Upload Processor
# ==============================================================================

def process_patient_bulk_upload(file_obj, nutritionist_user):
    """
    Parses an uploaded .xlsx / .xls file and creates User, UserProfile, optional LabReport,
    and assigns all created patients to nutritionist_user.
    
    Returns a dictionary summarizing:
    - total_rows
    - created_count
    - failed_count
    - created_patients: list of dicts
    - errors: list of { row: N, email: "...", error: "..." }
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {
            "success": False,
            "detail": f"Failed to read Excel file. Please ensure it is a valid .xlsx file. Error: {str(e)}",
            "total_rows": 0,
            "created_count": 0,
            "failed_count": 0,
            "errors": [{"row": 0, "error": f"Invalid Excel file format: {str(e)}"}]
        }

    # Pick the 'Patient Data' worksheet if present, else active sheet
    ws = wb["Patient Data"] if "Patient Data" in wb.sheetnames else wb.active

    # Read header row
    headers = []
    header_row_idx = 1
    for cell in ws[header_row_idx]:
        if cell.value:
            norm = normalize_header(cell.value)
            key = HEADER_TO_KEY.get(norm, norm)
            headers.append(key)
        else:
            headers.append(None)

    # If first row didn't match 'full_name' or 'email', check second row
    if "full_name" not in headers and "email" not in headers:
        header_row_idx = 2
        headers = []
        for cell in ws[header_row_idx]:
            if cell.value:
                norm = normalize_header(cell.value)
                key = HEADER_TO_KEY.get(norm, norm)
                headers.append(key)
            else:
                headers.append(None)

    if "full_name" not in headers or "email" not in headers:
        return {
            "success": False,
            "detail": "Missing mandatory columns in Excel file. Must include 'Full Name' and 'Email'. Please download and use the official template.",
            "total_rows": 0,
            "created_count": 0,
            "failed_count": 0,
            "errors": [{"row": 1, "error": "Headers 'Full Name' and 'Email' were not found."}]
        }

    rows_to_process = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=header_row_idx + 1, values_only=True), start=header_row_idx + 1):
        # Skip completely empty rows
        if not any(row):
            continue

        row_dict = {}
        for col_idx, col_key in enumerate(headers):
            if col_key and col_idx < len(row):
                row_dict[col_key] = row[col_idx]
        
        # Check if the row has at least an email or full_name
        if not row_dict.get("email") and not row_dict.get("full_name"):
            continue

        rows_to_process.append((row_idx, row_dict))

    if not rows_to_process:
        return {
            "success": False,
            "detail": "The uploaded Excel file contains no patient data rows.",
            "total_rows": 0,
            "created_count": 0,
            "failed_count": 0,
            "errors": []
        }

    created_patients = []
    errors = []

    # Batch process rows
    for row_idx, row_data in rows_to_process:
        try:
            full_name = str(row_data.get("full_name") or "").strip()
            raw_email = str(row_data.get("email") or "").strip().lower()

            # 1. Validate Required Fields
            if not full_name:
                errors.append({"row": row_idx, "name": "N/A", "email": raw_email or "N/A", "error": "Full Name is required."})
                continue

            if not raw_email:
                errors.append({"row": row_idx, "name": full_name, "email": "N/A", "error": "Email is required."})
                continue

            try:
                validate_email(raw_email)
            except ValidationError:
                errors.append({"row": row_idx, "name": full_name, "email": raw_email, "error": f"Invalid email format: '{raw_email}'"})
                continue

            # 2. Check if user with email already exists
            if User.objects.filter(email=raw_email).exists():
                existing_user = User.objects.get(email=raw_email)
                # If existing user is a patient, make sure they are assigned to nutritionist
                if existing_user.role == "user":
                    PatientAssignment.objects.get_or_create(
                        nutritionist=nutritionist_user,
                        patient=existing_user
                    )
                    errors.append({"row": row_idx, "name": full_name, "email": raw_email, "error": f"Email '{raw_email}' is already registered (Patient assigned to your roster)."})
                else:
                    errors.append({"row": row_idx, "name": full_name, "email": raw_email, "error": f"Account with email '{raw_email}' already exists with role '{existing_user.role}'."})
                continue

            # 3. Extract & Clean Profile Fields
            password = str(row_data.get("password") or "").strip() or "Default@123"
            mobile_number = str(row_data.get("mobile_number") or "").strip() or None
            dob = parse_date_value(row_data.get("date_of_birth"))
            
            raw_gender = clean_choice_key(row_data.get("gender"))
            gender = GENDER_MAP.get(raw_gender, "female" if "f" in raw_gender else "male" if raw_gender else "other")
            
            country = str(row_data.get("country") or "").strip() or None
            city = str(row_data.get("city") or "").strip() or None
            occupation = str(row_data.get("occupation") or "").strip()

            height_cm = parse_float_value(row_data.get("height_cm"))
            weight_kg = parse_float_value(row_data.get("weight_kg"))

            raw_activity = clean_choice_key(row_data.get("activity_level"))
            activity_level = ACTIVITY_MAP.get(raw_activity, "moderately_active")

            raw_goal = clean_choice_key(row_data.get("goal"))
            goal = GOAL_MAP.get(raw_goal, "lose_weight")

            raw_diet = clean_choice_key(row_data.get("diet_type"))
            diet_type = DIET_MAP.get(raw_diet, "vegetarian")

            allergies = str(row_data.get("allergies") or "").strip()
            is_diabetic = parse_bool_value(row_data.get("is_diabetic"))
            is_hypertensive = parse_bool_value(row_data.get("is_hypertensive"))
            has_heart_condition = parse_bool_value(row_data.get("has_heart_condition"))
            has_thyroid_disorder = parse_bool_value(row_data.get("has_thyroid_disorder"))
            has_arthritis = parse_bool_value(row_data.get("has_arthritis"))
            has_gastric_issues = parse_bool_value(row_data.get("has_gastric_issues"))
            other_chronic_condition = str(row_data.get("other_chronic_condition") or "").strip()
            family_history = str(row_data.get("family_history") or "").strip()

            is_pregnant = parse_bool_value(row_data.get("is_pregnant"))
            due_date = parse_date_value(row_data.get("due_date")) if is_pregnant else None
            is_breastfeeding = parse_bool_value(row_data.get("is_breastfeeding"))

            # Men cannot be marked pregnant/breastfeeding
            if gender == "male":
                is_pregnant = False
                due_date = None
                is_breastfeeding = False

            # 4. Extract Lab Report Fields
            lab_fields = {
                "fasting_blood_sugar": parse_float_value(row_data.get("fasting_blood_sugar")),
                "postprandial_sugar": parse_float_value(row_data.get("postprandial_sugar")),
                "hba1c": parse_float_value(row_data.get("hba1c")),
                "blood_pressure_systolic": parse_int_value(row_data.get("blood_pressure_systolic")),
                "blood_pressure_diastolic": parse_int_value(row_data.get("blood_pressure_diastolic")),
                "ldl_cholesterol": parse_float_value(row_data.get("ldl_cholesterol")),
                "hdl_cholesterol": parse_float_value(row_data.get("hdl_cholesterol")),
                "triglycerides": parse_float_value(row_data.get("triglycerides")),
                "tsh": parse_float_value(row_data.get("tsh")),
                "vitamin_d3": parse_float_value(row_data.get("vitamin_d3")),
                "vitamin_b12": parse_float_value(row_data.get("vitamin_b12")),
                "uric_acid": parse_float_value(row_data.get("uric_acid")),
                "creatinine": parse_float_value(row_data.get("creatinine")),
                "urea": parse_float_value(row_data.get("urea")),
                "alt": parse_float_value(row_data.get("alt")),
                "ast": parse_float_value(row_data.get("ast")),
            }
            # Only create lab report if at least one biomarker was provided
            has_lab_data = any(v is not None for v in lab_fields.values())
            lab_report_date = parse_date_value(row_data.get("lab_report_date")) or (date.today() if has_lab_data else None)

            # 5. Atomic Creation
            with transaction.atomic():
                user = User.objects.create_user(
                    email=raw_email,
                    full_name=full_name,
                    password=password,
                    role="user"
                )

                UserProfile.objects.create(
                    user=user,
                    date_of_birth=dob,
                    country=country,
                    city=city,
                    mobile_number=mobile_number,
                    gender=gender,
                    occupation=occupation,
                    height_cm=height_cm,
                    weight_kg=weight_kg,
                    activity_level=activity_level,
                    goal=goal,
                    diet_type=diet_type,
                    allergies=allergies,
                    is_diabetic=is_diabetic,
                    is_hypertensive=is_hypertensive,
                    has_heart_condition=has_heart_condition,
                    has_thyroid_disorder=has_thyroid_disorder,
                    has_arthritis=has_arthritis,
                    has_gastric_issues=has_gastric_issues,
                    other_chronic_condition=other_chronic_condition,
                    family_history=family_history,
                    is_pregnant=is_pregnant,
                    due_date=due_date,
                    is_breastfeeding=is_breastfeeding
                )

                if has_lab_data:
                    LabReport.objects.create(
                        user=user,
                        report_date=lab_report_date,
                        height_cm=height_cm,
                        weight_kg=weight_kg,
                        **lab_fields
                    )

                PatientAssignment.objects.update_or_create(
                    patient=user,
                    defaults={"nutritionist": nutritionist_user}
                )

                created_patients.append({
                    "id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "goal": goal,
                    "date_of_birth": str(dob) if dob else "",
                    "created_at": user.date_joined.isoformat() if hasattr(user, "date_joined") else None
                })

        except Exception as row_exc:
            errors.append({"row": row_idx, "email": row_data.get("email", "N/A"), "error": str(row_exc)})

    return {
        "success": True,
        "total_rows": len(rows_to_process),
        "created_count": len(created_patients),
        "failed_count": len(errors),
        "created_patients": created_patients,
        "errors": errors
    }
