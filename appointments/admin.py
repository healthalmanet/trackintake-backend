from django.contrib import admin, messages
from datetime import datetime, timedelta
from .models import AvailabilitySlot
from .forms import AvailabilitySlotAdminForm
from django.contrib import admin
from .models import Appointment
from nutritionist.models import NutritionistProfile
from user.models import User

@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    form = AvailabilitySlotAdminForm

    list_display = (
        "nutritionist",
        "date",
        "start_time",
        "end_time",
        "is_booked",
    )
    list_filter = ("nutritionist", "date", "is_booked")
    search_fields = ("nutritionist__email",)

    fieldsets = (
        ("Slot Details", {
            "fields": (
                "nutritionist",
                "date",
                ("start_time", "end_time"),
                "slot_duration",
                "is_booked",
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        If slot_duration is provided → generate multiple slots
        Otherwise → normal single-slot save
        """
        duration = form.cleaned_data.get("slot_duration")

        if duration:
            start_dt = datetime.combine(obj.date, obj.start_time)
            end_dt = datetime.combine(obj.date, obj.end_time)

            slots_created = 0

            while start_dt + timedelta(minutes=duration) <= end_dt:
                AvailabilitySlot.objects.create(
                    nutritionist=obj.nutritionist,
                    date=obj.date,
                    start_time=start_dt.time(),
                    end_time=(start_dt + timedelta(minutes=duration)).time(),
                    is_booked=False,
                )
                start_dt += timedelta(minutes=duration)
                slots_created += 1

            messages.success(
                request,
                f"{slots_created} slots generated successfully."
            )

        else:
            # Single slot save
            super().save_model(request, obj, form, change)
            messages.success(request, "Slot saved successfully.")

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "nutritionist",
        "appointment_category",
        "assigned_by",
        "status",
        "created_at",
    )

    readonly_fields = (
        "patient",
        "slot",
        "appointment_category",
        "selected_expert",
        "created_at",
    )

    fieldsets = (
        ("Appointment Info", {
            "fields": (
                "patient",
                "appointment_category",
                "selected_expert",
                "assigned_by",
                "status",
            )
        }),
        ("Admin Assignment", {
            "fields": ("nutritionist",)
        }),
        ("Slot", {
            "fields": ("slot",)
        }),
        ("Meeting", {
            "fields": (
                "appointment_type",
                "meeting_link",
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        if change and "nutritionist" in form.changed_data:
            obj.assigned_by = "ADMIN"
        super().save_model(request, obj, form, change)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        # 🔥 selected_expert → ONLY EXPERT doctors
        if db_field.name == "selected_expert":
            kwargs["queryset"] = User.objects.filter(
                nutritionist_profile__nutritionist_type=NutritionistProfile.NutritionistType.EXPERT
            )

        # nutritionist field → all nutritionists
        if db_field.name == "nutritionist":
            kwargs["queryset"] = User.objects.filter(role="nutritionist")

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
