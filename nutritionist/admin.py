# ─── In nutritionist/admin.py ─────────────────────────────────────────────────
# Replace the existing file with this — adds a one-click verify action

from django.contrib import admin
from .models import NutritionistProfile


class NutritionistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "get_email",
        "nutritionist_type",
        "is_verified",
        "is_virtual_enabled",
    )
    list_filter = (
        "nutritionist_type",
        "is_verified",
        "is_virtual_enabled",
    )
    search_fields = ("user__email", "user__full_name")
    list_editable = ("is_verified",)   # ← admin can toggle directly in the list
    actions = ["verify_nutritionists", "unverify_nutritionists"]

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email

    @admin.action(description="✅ Verify selected nutritionists")
    def verify_nutritionists(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} nutritionist(s) verified successfully.")

    @admin.action(description="❌ Unverify selected nutritionists")
    def unverify_nutritionists(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} nutritionist(s) unverified.")