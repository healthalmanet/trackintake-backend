from rest_framework import serializers
from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "price",
            "duration_days",
            "appointment_allowed",
            "BMI_Calculator_allowed",   # ← added
            "Fat_Calculator_allowed",
            "ai_diet_allowed",
            "expert_consults",
            "inhouse_consults",
        ]
