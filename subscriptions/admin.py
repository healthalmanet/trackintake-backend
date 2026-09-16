from django.contrib import admin
from django.utils.html import format_html
from .models import Plan, UserSubscription, Payment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "get_plan_badge",
        "price",
        "duration_days",
        "get_feature_summary",
        "is_active",
    )

    list_filter = (
        "plan_type",
        "is_active",
        "nutri_ai_diet_allowed",
        "nutri_bulk_upload_allowed",
        "nutri_lab_reports_allowed",
        "nutri_smart_assistant_allowed",
        "nutri_online_appointment_allowed",
        "nutri_offline_appointment_allowed",
        "meal_log_allowed",
        "water_intake_allowed",
        "weight_tracker_allowed",
    )

    search_fields = ("name",)

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "plan_type", "price", "duration_days", "is_active"),
            "description": "Specify general tier details. Changing Target Audience dynamically switches available feature options below."
        }),
        ("👤 Patient Features & Access (Only for Patient Plans)", {
            "classes": ("patient-features-group",),
            "fields": (
                "meal_log_allowed",
                "water_intake_allowed",
                "weight_tracker_allowed",
                "nutrition_search_allowed",
                "custom_reminder_allowed",
                "ai_diet_allowed",
                "appointment_allowed",
                "chat_allowed",
                "BMI_Calculator_allowed",
                "Fat_Calculator_allowed",
            ),
            "description": "Select health tracking and member features enabled for patient subscribers."
        }),
        ("👤 Patient Consultation Allowances (Only for Patient Plans)", {
            "classes": ("patient-limits-group",),
            "fields": (
                "inhouse_consults",
                "expert_consults",
            ),
            "description": "Number of in-house and expert consultations included in this tier (Enter 0 for Unlimited consultations)."
        }),
        ("🧑‍⚕️ Nutritionist Features & Practitioner Controls (Only for Nutritionist Plans)", {
            "classes": ("nutritionist-features-group",),
            "fields": (
                "nutri_ai_diet_allowed",
                "nutri_manual_diet_allowed",
                "nutri_bulk_upload_allowed",
                "nutri_lab_reports_allowed",
                "nutri_chat_allowed",
                "nutri_smart_assistant_allowed",
                "nutri_online_appointment_allowed",
                "nutri_offline_appointment_allowed",
                "nutri_export_reports_allowed",
            ),
            "description": "Granularly toggle clinical tools, AI diet formulation, bulk patient upload, lab test analysis, and patient messaging access."
        }),
        ("🧑‍⚕️ Nutritionist Patient Capacity Limits (Only for Nutritionist Plans)", {
            "classes": ("nutritionist-limits-group",),
            "fields": (
                "nutri_max_patients",
            ),
            "description": "Maximum number of assigned active patients allowed under this practitioner tier (0 = Unlimited)."
        }),
    )

    class Media:
        js = ("subscriptions/js/plan_admin.js",)
        css = {
            "all": ("subscriptions/css/plan_admin.css",)
        }

    @admin.display(description="Target Audience")
    def get_plan_badge(self, obj):
        if obj.plan_type == "nutritionist":
            return format_html(
                '<span style="padding:4px 10px; border-radius:12px; font-weight:bold; font-size:11px; background:#0284c7; color:white; display:inline-flex; align-items:center; gap:4px;">🧑‍⚕️ Nutritionist</span>'
            )
        return format_html(
            '<span style="padding:4px 10px; border-radius:12px; font-weight:bold; font-size:11px; background:#059669; color:white; display:inline-flex; align-items:center; gap:4px;">👤 Patient</span>'
        )

    @admin.display(description="Enabled Features")
    def get_feature_summary(self, obj):
        if obj.plan_type == "nutritionist":
            features = []
            if obj.nutri_ai_diet_allowed:
                features.append("AI Diet")
            if obj.nutri_manual_diet_allowed:
                features.append("Manual Diet")
            if obj.nutri_bulk_upload_allowed:
                features.append("Bulk Upload")
            if obj.nutri_lab_reports_allowed:
                features.append("Lab Reports")
            if obj.nutri_smart_assistant_allowed:
                features.append("Nutro AI")
            if obj.nutri_chat_allowed:
                features.append("Chat")
            if obj.nutri_online_appointment_allowed:
                features.append("Online Consult")
            if obj.nutri_offline_appointment_allowed:
                features.append("Clinic Consult")
            if obj.nutri_max_patients:
                features.append(f"{obj.nutri_max_patients} Patients")
            else:
                features.append("Unlimited Patients")

            badges = "".join([
                f'<span style="padding:2px 7px; margin:2px; border-radius:6px; font-size:10px; font-weight:600; background:#e0f2fe; color:#0369a1; display:inline-block;">{f}</span>'
                for f in features
            ])
            return format_html(badges)
        else:
            features = []
            if obj.meal_log_allowed:
                features.append("Meal Log")
            if obj.water_intake_allowed:
                features.append("Water")
            if obj.weight_tracker_allowed:
                features.append("Weight")
            if obj.ai_diet_allowed:
                features.append("AI Diet")
            if obj.chat_allowed:
                features.append("Chat")
            if obj.appointment_allowed:
                features.append("Appointments")

            badges = "".join([
                f'<span style="padding:2px 7px; margin:2px; border-radius:6px; font-size:10px; font-weight:600; background:#dcfce7; color:#15803d; display:inline-block;">{f}</span>'
                for f in features
            ])
            return format_html(badges)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "start_date", "end_date", "is_active")
    list_filter = ("is_active", "plan__plan_type", "plan")
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
    list_filter = ("status", "plan__plan_type")
    search_fields = ("razorpay_order_id", "razorpay_payment_id", "user__email", "pending_email")