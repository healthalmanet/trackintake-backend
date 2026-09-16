from rest_framework import serializers
from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "plan_type",
            "price",
            "duration_days",

            # Patient Feature flags
            "meal_log_allowed",
            "water_intake_allowed",
            "weight_tracker_allowed",
            "custom_reminder_allowed",
            "chat_allowed",
            "nutrition_search_allowed",

            # Core features
            "appointment_allowed",
            "ai_diet_allowed",
            "BMI_Calculator_allowed",
            "Fat_Calculator_allowed",

            # Patient Limits
            "expert_consults",
            "inhouse_consults",
            "inhouse_consultation_fee",
            "expert_consultation_fee",

            # Nutritionist Practitioner Feature flags
            "nutri_ai_diet_allowed",
            "nutri_manual_diet_allowed",
            "nutri_bulk_upload_allowed",
            "nutri_lab_reports_allowed",
            "nutri_chat_allowed",
            "nutri_smart_assistant_allowed",
            "nutri_online_appointment_allowed",
            "nutri_offline_appointment_allowed",
            "nutri_export_reports_allowed",
            "nutri_max_patients",
        ]