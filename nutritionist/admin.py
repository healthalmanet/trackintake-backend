# nutritionist/admin.py

from django.contrib import admin
from .models import NutritionistProfile


class NutritionistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "nutritionist_type",
        "is_verified",
        "is_virtual_enabled",
    )
    list_filter = (
        "nutritionist_type",
        "is_verified",
        "is_virtual_enabled",
    )
    search_fields = ("user__email",)
