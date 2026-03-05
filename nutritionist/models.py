from django.db import models

from django.conf import settings
from django.utils import timezone





##############Nutritionist Recommendations
# class NutritionistProfile(models.Model):
#     user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="nutritionist_profile"
#     )
#     is_virtual_enabled = models.BooleanField(default=False)

#     def __str__(self):
#         return f"NutritionistProfile({self.user.email})"
# #Patient Nutritionist Assignment



class PatientAssignment(models.Model):
    nutritionist = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='assigned_patients',
        
        # === EDITED LINE ===
        # We are now filtering by the 'role' field, which exists on your user model.
        # Make sure the role name matches exactly what you have in your user model's choices.
        limit_choices_to={'role': 'nutritionist'} 
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='assigned_nutritionist'
    )
    
    assigned_at = models.DateField(
        verbose_name="Assignment Date",
        default=timezone.now,
        help_text="The date the patient was officially assigned. Defaults to today, but can be changed."
    )

    class Meta:
        # Ensures a patient can only be assigned to one nutritionist at a time.
        unique_together = ('patient', 'nutritionist') 
        ordering = ['-assigned_at'] # Shows the most recent assignments first

    def __str__(self):
        # Example: "Dr. Smith assigned Patient John Doe on 2023-10-27"
        # Using .get_full_name() or a similar method is better if it exists.
        # If not, fallback to username.
        nutritionist_name = self.nutritionist.full_name if hasattr(self.nutritionist, 'full_name') else self.nutritionist.username
        patient_name = self.patient.full_name if hasattr(self.patient, 'full_name') else self.patient.username
        return f"{nutritionist_name} assigned {patient_name} on {self.assigned_at.strftime('%Y-%m-%d')}"
    
# nutritionist/models.py

# nutritionist/models.py

from django.db import models
from django.conf import settings


class NutritionistProfile(models.Model):

    class NutritionistType(models.TextChoices):
        INHOUSE = "inhouse", "In-house"
        EXPERT = "expert", "Expert"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nutritionist_profile"
    )

    nutritionist_type = models.CharField(
        max_length=20,
        choices=NutritionistType.choices,
        default=NutritionistType.INHOUSE
    )

    is_virtual_enabled = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} ({self.get_nutritionist_type_display()})"
