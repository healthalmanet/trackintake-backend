from django.contrib import admin
from django.utils import timezone
from .models import NutritionistProfile


@admin.register(NutritionistProfile)
class NutritionistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "get_full_name",
        "get_email",
        "get_phone_number",
        "nutritionist_type",
        "is_verified",
        "verified_at",
        "is_virtual_enabled",
        "created_at",
    )
    list_filter = (
        "is_verified",
        "nutritionist_type",
        "is_virtual_enabled",
        "verified_at",
        "created_at",
    )
    search_fields = ("user__email", "user__full_name", "user__phone_number")
    list_editable = ("is_verified",)
    readonly_fields = ("verified_at", "created_at", "updated_at")
    actions = ["verify_nutritionists", "unverify_nutritionists"]

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return obj.user.full_name or "N/A"

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description="Phone Number")
    def get_phone_number(self, obj):
        return obj.user.phone_number or "N/A"

    @admin.action(description="✅ Verify selected nutritionists")
    def verify_nutritionists(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(is_verified=True, verified_at=now)
        self.message_user(request, f"{updated} nutritionist(s) verified successfully.")

    @admin.action(description="❌ Unverify selected nutritionists")
    def unverify_nutritionists(self, request, queryset):
        updated = queryset.update(is_verified=False, verified_at=None)
        self.message_user(request, f"{updated} nutritionist(s) unverified.")