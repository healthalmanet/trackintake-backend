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
from utils.cloud import CustomCloudinaryStorage


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
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Verified At")
    
    # Appointment Availability & Location
    is_online_available = models.BooleanField(default=True, verbose_name="Available for Online Appointment")
    is_offline_available = models.BooleanField(default=False, verbose_name="Available for Offline Appointment")
    offline_location = models.TextField(blank=True, null=True, help_text="Clinic/Practice address for offline appointments")

    # Approved Pricing & Payment Settings
    online_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Current approved online appointment price")
    offline_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Current approved offline appointment price")
    offline_payment_required = models.BooleanField(default=True, help_text="Require payment upfront for offline appointments (True=Pay online, False=Pay at clinic/cash)")

    # Pending Price Approval Workflow
    class PriceApprovalStatus(models.TextChoices):
        APPROVED = "approved", "Approved"
        PENDING = "pending", "Pending Approval"
        REJECTED = "rejected", "Rejected"

    pending_online_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Pending requested online price")
    pending_offline_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Pending requested offline price")
    pending_offline_payment_required = models.BooleanField(null=True, blank=True, help_text="Pending offline payment requirement setting")
    price_approval_status = models.CharField(
        max_length=20,
        choices=PriceApprovalStatus.choices,
        default=PriceApprovalStatus.APPROVED
    )
    price_rejection_reason = models.TextField(blank=True, null=True)

    # Professional Credentials Information
    professional_title = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Clinical Nutritionist / Dietitian")
    qualification = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. MSc Nutrition & Dietetics")
    registration_number = models.CharField(max_length=100, blank=True, null=True, help_text="NIN/State Registration No.")
    issuing_authority = models.CharField(max_length=255, blank=True, null=True, help_text="Relevant professional body")
    years_of_experience = models.PositiveIntegerField(default=0, blank=True, null=True, help_text="Years of professional practice")
    current_organization = models.CharField(max_length=255, blank=True, null=True, help_text="Current clinic/hospital/organization name")
    professional_bio = models.TextField(blank=True, null=True, help_text="Short introduction")
    languages_spoken = models.JSONField(default=list, blank=True, help_text="List of languages spoken")

    # Specializations
    specializations = models.JSONField(default=list, blank=True, help_text="List of specializations selected")

    # Verification Documents (Cloudinary Storage)
    qualification_certificate = models.FileField(upload_to="nutritionist/certificates/", storage=CustomCloudinaryStorage(), blank=True, null=True)
    registration_certificate = models.FileField(upload_to="nutritionist/certificates/", storage=CustomCloudinaryStorage(), blank=True, null=True)
    government_id = models.FileField(upload_to="nutritionist/documents/", storage=CustomCloudinaryStorage(), blank=True, null=True)
    experience_certificate = models.FileField(upload_to="nutritionist/certificates/", storage=CustomCloudinaryStorage(), blank=True, null=True)
    additional_certifications = models.FileField(upload_to="nutritionist/certificates/", storage=CustomCloudinaryStorage(), blank=True, null=True)
    profile_photo = models.ImageField(upload_to="nutritionist/photos/", storage=CustomCloudinaryStorage(), blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.is_verified and not self.verified_at:
            self.verified_at = timezone.now()
        elif not self.is_verified:
            self.verified_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} ({self.get_nutritionist_type_display()})"
