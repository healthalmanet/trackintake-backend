from django.db import models
from django.utils import timezone    
from django.conf import settings # ⬅️ Import Django settings
from cloudinary_storage.storage import MediaCloudinaryStorage
from utils.cloud import CustomCloudinaryStorage


from datetime import date, timedelta
from django.core.exceptions import ValidationError # ⬅️ Import this


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="userprofile")
    # Basic Info
    date_of_birth = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female"), ("other", "Other")])

    occupation = models.CharField(max_length=100, blank=True, help_text="e.g., Software Developer, Teacher, Construction Worker")
    
    # Core Anthropometry
    height_cm = models.FloatField(null=True, blank=True, help_text="User's current height in cm")
    weight_kg = models.FloatField(null=True, blank=True, help_text="User's current weight in kg")

    # Lifestyle
    activity_level = models.CharField(max_length=50, choices=[
        ("Sedentary", "Sedentary (little or no exercise)"),
        ("Lightly Active", "Lightly Active (light exercise/sports 1-3 days/week)"),
        ("Moderately Active", "Moderately Active (moderate exercise/sports 3-5 days/week)"),
        ("Very Active", "Very Active (hard exercise/sports 6-7 days a week)"),
        ("Extra Active", "Extra Active (very hard exercise/physical job)"),
    ], null=True, blank=True)
    goal = models.CharField(max_length=20, choices=[
        ("Lose Weight", "Lose Weight"),
        ("Maintain Weight", "Maintain Weight"),
        ("Gain Weight", "Gain Weight")
    ], null=True, blank=True)

    # Dietary Preferences and Restrictions
    diet_type = models.CharField(max_length=20, choices=[
        ("Vegetarian", "Vegetarian"), ("Non Vegetarian", "Non Vegetarian"),
        ("Vegan", "Vegan"), ("Eggetarian", "Eggetarian"),
        ("Keto", "Keto"), ("Other", "Other"),
    ], default="other")
    allergies = models.TextField(blank=True, help_text="List known food allergies, separated by commas.")

    # Known Medical Conditions (Flags for the Rule Engine)
    is_diabetic = models.BooleanField(default=False, verbose_name="Known Diabetic Condition")
    is_hypertensive = models.BooleanField(default=False, verbose_name="Known Hypertension (High BP)")
    has_heart_condition = models.BooleanField(default=False, verbose_name="Known Heart Condition (CVD)")
    has_thyroid_disorder = models.BooleanField(default=False, verbose_name="Known Thyroid Disorder")
    has_arthritis = models.BooleanField(default=False, verbose_name="Known Arthritis (RA/OA/Gout)")
    has_gastric_issues = models.BooleanField(default=False, verbose_name="Known Gastric Issues (IBS/GERD)")

    # Additional Context
    other_chronic_condition = models.TextField(blank=True, help_text="Describe any other long-term health conditions.")
    family_history = models.TextField(blank=True, help_text="Describe significant family history of diseases.")


      # --- NEW: PREGNANCY & POSTPARTUM FIELDS (Add this entire block) ---
    is_pregnant = models.BooleanField(
        default=False, verbose_name="Currently Pregnant"
    )
    due_date = models.DateField(
        null=True, blank=True, help_text="The estimated due date, if pregnant."
    )
    is_breastfeeding = models.BooleanField(
        default=False, verbose_name="Currently Breastfeeding"
    )

    def __str__(self):
        return f"Profile for {self.user.username}"

    # --- NEW: HELPER PROPERTY TO CALCULATE TRIMESTER ---
    @property
    def current_trimester(self):
        if not self.is_pregnant or not self.due_date:
            return None
        
        today = date.today()
        weeks_pregnant = 40 - ((self.due_date - today) / timedelta(weeks=1))
        
        if weeks_pregnant < 14:
            return 1
        elif 14 <= weeks_pregnant < 28:
            return 2
        else:
            return 3



    def __str__(self):
        return f"Profile for {self.user.full_name}"
    
    @property
    def bmi(self):
        if self.height_cm and self.weight_kg:
            return round(self.weight_kg / ((self.height_cm / 100) ** 2), 2)
        return 0


# This is your existing UserProfile model, updated with the new features and validation.
# class UserProfile(models.Model):
#     # --- Existing Fields (No changes needed here) ---
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="userprofile")
#     date_of_birth = models.DateField(null=True, blank=True)
#     country = models.CharField(max_length=100, blank=True, null=True)
#     mobile_number = models.CharField(max_length=15, blank=True, null=True)
#     gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female"), ("other", "Other")])
#     occupation = models.CharField(max_length=100, blank=True, help_text="e.g., Software Developer, Teacher")
#     height_cm = models.FloatField(null=True, blank=True, help_text="User's current height in cm")
#     weight_kg = models.FloatField(null=True, blank=True, help_text="User's current weight in kg")
#     activity_level = models.CharField(max_length=50, choices=[("Sedentary", "Sedentary"), ("Lightly Active", "Lightly Active"), ("Moderately Active", "Moderately Active"), ("Very Active", "Very Active"), ("Extra Active", "Extra Active")], null=True, blank=True)
#     goal = models.CharField(max_length=20, choices=[("Lose Weight", "Lose Weight"), ("Maintain Weight", "Maintain Weight"), ("Gain Weight", "Gain Weight")], null=True, blank=True)
#     diet_type = models.CharField(max_length=20, choices=[("Vegetarian", "Vegetarian"), ("Non Vegetarian", "Non Vegetarian"), ("Vegan", "Vegan"), ("Eggetarian", "Eggetarian")], default="other")
#     allergies = models.TextField(blank=True, help_text="List known food allergies, separated by commas.")
#     is_diabetic = models.BooleanField(default=False, verbose_name="Known Diabetic Condition")
#     is_hypertensive = models.BooleanField(default=False, verbose_name="Known Hypertension (High BP)")
#     has_heart_condition = models.BooleanField(default=False, verbose_name="Known Heart Condition (CVD)")
#     has_thyroid_disorder = models.BooleanField(default=False, verbose_name="Known Thyroid Disorder")
#     has_arthritis = models.BooleanField(default=False, verbose_name="Known Arthritis (RA/OA/Gout)")
#     has_gastric_issues = models.BooleanField(default=False, verbose_name="Known Gastric Issues (IBS/GERD)")
#     other_chronic_condition = models.TextField(blank=True, help_text="Describe any other long-term health conditions.")
#     family_history = models.TextField(blank=True, help_text="Describe significant family history of diseases.")

#     # --- NEW: Pregnancy & Postpartum Fields ---
#     is_pregnant = models.BooleanField(default=False, verbose_name="Currently Pregnant")
#     due_date = models.DateField(null=True, blank=True, help_text="The estimated due date, if pregnant.")
#     is_breastfeeding = models.BooleanField(default=False, verbose_name="Currently Breastfeeding")

#     # --- NEW: CRITICAL Model-Level Validation ---
#     def clean(self):
#         """
#         Enforces business rules at the database level. This is the ultimate safety net
#         to prevent corrupted or illogical data from being saved.
#         """
#         super().clean()
#         is_male = self.gender and self.gender.lower() == 'male'

#         # Rule 1: A user with gender 'Male' cannot be pregnant, breastfeeding, or have a due date.
#         if is_male:
#             if self.is_pregnant:
#                 raise ValidationError({'is_pregnant': 'A user with gender "Male" cannot be marked as pregnant.'})
#             if self.due_date:
#                 raise ValidationError({'due_date': 'A user with gender "Male" cannot have a due date.'})
#             if self.is_breastfeeding:
#                 raise ValidationError({'is_breastfeeding': 'A user with gender "Male" cannot be breastfeeding.'})

#         # Rule 2: A due date should only be present if the user is marked as pregnant.
#         if self.due_date and not self.is_pregnant:
#             raise ValidationError({'due_date': 'A due date can only be set if the user is marked as pregnant.'})

#     def save(self, *args, **kwargs):
#         # Ensure the clean method is called automatically on every save.
#         self.full_clean()
#         super().save(*args, **kwargs)

#     # --- Helper property for calculating trimester ---
#     @property
#     def current_trimester(self):
#         if not self.is_pregnant or not self.due_date:
#             return None
#         weeks_pregnant = 40 - ((self.due_date - date.today()) / timedelta(weeks=1))
#         if weeks_pregnant < 14: return 1
#         elif 14 <= weeks_pregnant < 28: return 2
#         else: return 3
    
#     @property
#     def bmi(self):
#         if self.height_cm and self.weight_kg:
#             return round(self.weight_kg / ((self.height_cm / 100) ** 2), 2)
#         return 0

#     def __str__(self):
#         # Make sure user has full_name attribute or use username
#         try:
#             return f"Profile for {self.user.full_name}"
#         except AttributeError:
#             return f"Profile for {self.user.username}"    
    
    
    
class LabReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lab_reports")
    report_date = models.DateField(default=timezone.now, help_text="The date the lab report was generated.")



    report_file = models.FileField(
        upload_to="reports/files/",
        storage=CustomCloudinaryStorage(),  # 👈 THIS IS CRUCIAL  # 👈 Force Cloudinary
        null=True, blank=True,
        help_text="Upload your lab report PDF, scanned reports, or documents"
    )


    weight_kg = models.FloatField(null=True, blank=True, help_text="Weight in kg at the time of the report.")
    height_cm = models.FloatField(null=True, blank=True, help_text="Height in cm at the time of the report.")
    waist_circumference_cm = models.FloatField(null=True, blank=True, help_text="Waist circumference in cm.")
    blood_pressure_systolic = models.PositiveIntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.PositiveIntegerField(null=True, blank=True)

    
    fasting_blood_sugar = models.FloatField(null=True, blank=True, help_text="mg/dL")
    postprandial_sugar = models.FloatField(null=True, blank=True, help_text="mg/dL")
    hba1c = models.FloatField(null=True, blank=True, help_text="%")
    
    ldl_cholesterol = models.FloatField(null=True, blank=True, help_text="mg/dL")
    hdl_cholesterol = models.FloatField(null=True, blank=True, help_text="mg/dL")
    triglycerides = models.FloatField(null=True, blank=True, help_text="mg/dL")

    crp = models.FloatField(null=True, blank=True, help_text="mg/L")
    esr = models.FloatField(null=True, blank=True, help_text="mm/hr")
    
    uric_acid = models.FloatField(null=True, blank=True, help_text="mg/dL")
    creatinine = models.FloatField(null=True, blank=True, help_text="mg/dL")
    urea = models.FloatField(null=True, blank=True, help_text="mg/dL")

    alt = models.FloatField(null=True, blank=True, help_text="U/L")
    ast = models.FloatField(null=True, blank=True, help_text="U/L")
    
    vitamin_d3 = models.FloatField(null=True, blank=True, help_text="ng/mL")
    vitamin_b12 = models.FloatField(null=True, blank=True, help_text="pg/mL")

    tsh = models.FloatField(null=True, blank=True, help_text="µIU/mL")

    class Meta:
        ordering = ['-report_date']

    def __str__(self):
        return f"Lab Report for {self.user.full_name} on {self.report_date}"


