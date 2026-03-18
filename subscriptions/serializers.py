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

            # Feature flags
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

            # Limits
            "expert_consults",
            "inhouse_consults",
        ]