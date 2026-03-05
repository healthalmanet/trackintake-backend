from django import forms
from datetime import datetime, timedelta
from .models import AvailabilitySlot

class AvailabilitySlotAdminForm(forms.ModelForm):
    # Extra fields (not stored in DB)
    slot_duration = forms.IntegerField(
        required=False,
        min_value=5,
        label="Slot Duration (minutes)",
        help_text="Used only when generating multiple slots"
    )

    class Meta:
        model = AvailabilitySlot
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        duration = cleaned_data.get("slot_duration")

        if start and end and start >= end:
            raise forms.ValidationError("End time must be after start time.")

        if duration and duration <= 0:
            raise forms.ValidationError("Slot duration must be positive.")

        return cleaned_data
