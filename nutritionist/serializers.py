from rest_framework import serializers
from user.models import User
from userProfile.models import UserProfile,LabReport
from userFood.models import UserMeal
from diet.models import DietRecommendation


#############------------------------------------------nutritonist serializer----------------------------######################
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'date_joined']  # ✅ Add full_name here
        read_only_fields = ['email', 'role', 'date_joined']  # Prevents accidental changes to email/role/date


class UserSerializer1(serializers.ModelSerializer):
    """
    Serializer for the custom User model.
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'date_joined', 'is_active']


class LabReportSerializer1(serializers.ModelSerializer):
    """
    Serializer for the LabReport model.
    """
    class Meta:
        model = LabReport
        # List all fields you want to expose from the lab report
        fields = [
            'id', 'report_date', 'weight_kg', 'height_cm', 'waist_circumference_cm',
            'blood_pressure_systolic', 'blood_pressure_diastolic',
            'fasting_blood_sugar', 'postprandial_sugar', 'hba1c',
            'ldl_cholesterol', 'hdl_cholesterol', 'triglycerides', 'crp', 'esr',
            'uric_acid', 'creatinine', 'urea', 'alt', 'ast', 'vitamin_d3',
            'vitamin_b12', 'tsh','report_file'
        ]


class PatientProfileSerializer1(serializers.ModelSerializer):
    """
    Serializer for the UserProfile model, designed for nutritionist view.
    """
    # Nest the user's basic info directly
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = UserProfile
        # List all fields from UserProfile you want to show
        fields = [
            'email', 'full_name', 'date_of_birth', 'gender', 'occupation',
            'height_cm', 'weight_kg', 'bmi', 'activity_level', 'goal',
            'diet_type', 'allergies', 'is_diabetic', 'is_hypertensive',
            'has_heart_condition', 'has_thyroid_disorder', 'has_arthritis',
            'has_gastric_issues', 'other_chronic_condition', 'family_history'
        ]

class UserMealSerializer1(serializers.ModelSerializer):
    """
    Serializer for patient's meal logs.
    """
    food_item_name = serializers.CharField(source='food_item.name', read_only=True, default='')

    class Meta:
        model = UserMeal
        fields = [
            'id', 'food_item_name', 'food_name', 'quantity', 'unit', 'meal_type',
            'consumed_at', 'date', 'calories', 'protein', 'carbs', 'fats'
        ]


class DietRecommendationWithPatientSerializer1(serializers.ModelSerializer):
    """
    Serializer for DietRecommendation that includes patient details.
    """
    patient_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = DietRecommendation
        fields = [
            'id', 'for_week_starting', 'status', 'created_at',
            'patient_info', 'meals', 'nutritionist_comment'
        ]
####################################################################----------------------------------------##########################



####--------patient Create Serializer-----------------######

class LabReportSerializer(serializers.ModelSerializer):

    report_file = serializers.FileField(required=False, allow_null=True)
    class Meta:
        model = LabReport
        exclude = ['user']













class CreatePatientSerializer(serializers.Serializer):

    # User fields
    email = serializers.EmailField()
    full_name = serializers.CharField()
    password = serializers.CharField(write_only=True, required=False, default="Default@123")

    # Profile fields
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.ChoiceField(choices=[("male", "Male"), ("female", "Female"), ("other", "Other")], required=False)
    mobile_number = serializers.CharField(required=False)
    country = serializers.CharField(required=False)
    occupation = serializers.CharField(required=False)
    height_cm = serializers.FloatField(required=False)
    weight_kg = serializers.FloatField(required=False)
    activity_level = serializers.ChoiceField(choices=[
        ("sedentary", "Sedentary (little or no exercise)"),
        ("lightly_active", "Lightly Active (light exercise/sports 1-3 days/week)"),
        ("moderately_active", "Moderately Active (moderate exercise/sports 3-5 days/week)"),
        ("very_active", "Very Active (hard exercise/sports 6-7 days a week)"),
        ("extra_active", "Extra Active (very hard exercise/physical job)"),
    ], required=False)
    goal = serializers.ChoiceField(choices=[
        ("lose_weight", "Lose Weight"),
        ("maintain", "Maintain Weight"),
        ("gain_weight", "Gain Weight")
    ], required=False)
    diet_type = serializers.ChoiceField(choices=[
        ("vegetarian", "Vegetarian"), ("non_vegetarian", "Non-Vegetarian"),
        ("vegan", "Vegan"), ("eggetarian", "Eggetarian"),
        ("keto", "Keto"), ("other", "Other"),
    ], required=False, default="other")
    allergies = serializers.CharField(required=False, allow_blank=True)
    is_diabetic = serializers.BooleanField(required=False)
    is_hypertensive = serializers.BooleanField(required=False)
    has_heart_condition = serializers.BooleanField(required=False)
    has_thyroid_disorder = serializers.BooleanField(required=False)
    has_arthritis = serializers.BooleanField(required=False)
    has_gastric_issues = serializers.BooleanField(required=False)
    other_chronic_condition = serializers.CharField(required=False, allow_blank=True)
    family_history = serializers.CharField(required=False, allow_blank=True)

    # Optional nested LabReport
    lab_report = LabReportSerializer(required=False)

    def create(self, validated_data):
        lab_data = validated_data.pop("lab_report", None)
        password = validated_data.pop("password", "Default@123")

        # Split user and profile fields
        user_fields = {
            "email": validated_data.pop("email"),
            "full_name": validated_data.pop("full_name"), # Default active status
        }

        profile_fields = validated_data

        # Create User
        user = User.objects.create_user(**user_fields, password=password)

        # Create Profile
        UserProfile.objects.create(user=user, **profile_fields)

        # Optional Lab Report
        if lab_data:
            LabReport.objects.create(user=user, **lab_data)

        return user
    


























class UserInfoSerializer(serializers.ModelSerializer):
    """
    A simple serializer to represent user information in nested responses.
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role']

class DietRecommendationDetailSerializer(serializers.ModelSerializer):
    """
    Provides a complete, detailed representation of a DietRecommendation,
    including nested user information and human-readable choices.
    """
    # Use the nested serializer for the 'user' field
    user = UserInfoSerializer(read_only=True)
    
    # Use a method field to show the display name of the status (e.g., "Pending Review")
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Use the nested serializer for the 'reviewed_by' field for clarity
    reviewed_by = UserInfoSerializer(read_only=True)

    class Meta:
        model = DietRecommendation
        fields = [
            # Core Fields
            'id',
            'user',
            'for_week_starting',
            'meals',
            
            # Review & Workflow Fields
            'status',
            'status_display', # Human-readable status
            'nutritionist_comment',
            'reviewed_by',
            
            # Retraining Pipeline Fields
            'user_profile_snapshot',
            'original_ai_plan',
            'approved_for_retraining',
            'nutritionist_retraining_notes',
            'was_used_for_retraining',
            
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'user', 'user_profile_snapshot', 'original_ai_plan',
            'was_used_for_retraining', 'created_at', 'updated_at'
        ]