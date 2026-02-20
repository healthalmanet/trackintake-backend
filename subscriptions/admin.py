from django.contrib import admin
from .models import Plan, UserSubscription, Payment

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "weight_tracker_allowed",
        "nutrition_search_allowed",
        "custom_reminder_allowed",
        "ai_diet_allowed",
        "appointment_allowed",
        "chat_allowed",
        "is_active",
    )

    list_filter = (
        "is_active",
        "weight_tracker_allowed",
        "nutrition_search_allowed",
        "custom_reminder_allowed",
        "ai_diet_allowed",
        "appointment_allowed",
        "chat_allowed",
    )

    search_fields = ("name",)
    list_editable = ("price", "is_active")
    ordering = ("price",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "price", "duration_days", "is_active")
        }),
        ("Features", {
            "fields": (
                "weight_tracker_allowed",
                "nutrition_search_allowed",
                "custom_reminder_allowed",
                "ai_diet_allowed",
                "appointment_allowed",
                "chat_allowed",
            )
        }),
        ("Limits", {
            "fields": ("expert_consults", "inhouse_consults")
        }),
    )



@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("is_active", "plan")
    search_fields = ("user__email",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "amount",
        "status",
        "razorpay_order_id",
        "razorpay_payment_id",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("razorpay_order_id", "razorpay_payment_id", "user__email")
