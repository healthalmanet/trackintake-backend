from django.contrib import admin
from .models import Plan, UserSubscription, Payment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "plan_type",
        "price",
        "duration_days",
        "inhouse_consultation_fee",  # ✅ ADD
        "expert_consultation_fee",
        "meal_log_allowed",        # ✅ ADD
        "water_intake_allowed",    # ✅ ADD
        "weight_tracker_allowed",
        "nutrition_search_allowed",
        "custom_reminder_allowed",
        "ai_diet_allowed",
        "appointment_allowed",
        "chat_allowed",
        "BMI_Calculator_allowed",
        "Fat_Calculator_allowed",
        "is_active",
    )

    list_filter = (
        "plan_type",
        "is_active",
        "meal_log_allowed",        # ✅ ADD
        "water_intake_allowed",    # ✅ ADD
        "weight_tracker_allowed",
        "nutrition_search_allowed",
        "custom_reminder_allowed",
        "ai_diet_allowed",
        "appointment_allowed",
        "chat_allowed",
        "BMI_Calculator_allowed",
        "Fat_Calculator_allowed",
    )

    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "plan_type", "price", "duration_days", "is_active")
        }),
        ("Features", {
            "fields": (
                "meal_log_allowed",        # ✅ ADD
                "water_intake_allowed",    # ✅ ADD
                "weight_tracker_allowed",
                "nutrition_search_allowed",
                "custom_reminder_allowed",
                "ai_diet_allowed",
                "appointment_allowed",
                "chat_allowed",
                "BMI_Calculator_allowed",
                "Fat_Calculator_allowed",
            )
        }),
        ("Limits", {
            "fields": ("expert_consults", "inhouse_consults","inhouse_consultation_fee","expert_consultation_fee")
        }),
    )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "start_date", "end_date", "is_active")
    list_filter = ("is_active", "plan")
    search_fields = ("user__email",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "pending_email",
        "plan",
        "amount",
        "status",
        "razorpay_order_id",
        "razorpay_payment_id",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("razorpay_order_id", "razorpay_payment_id", "user__email", "pending_email")