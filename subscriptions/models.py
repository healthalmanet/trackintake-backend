from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

User = settings.AUTH_USER_MODEL


class Plan(models.Model):

    class PlanType(models.TextChoices):
        PATIENT = "patient", "Patient"
        NUTRITIONIST = "nutritionist", "Nutritionist"

    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField()
    duration_days = models.PositiveIntegerField()

    # ── NEW: separates patient plans from nutritionist plans ──────────────────
    plan_type = models.CharField(
        max_length=20,
        choices=PlanType.choices,
        default=PlanType.PATIENT,
    )

    weight_tracker_allowed = models.BooleanField(default=False)
    nutrition_search_allowed = models.BooleanField(default=False)
    custom_reminder_allowed = models.BooleanField(default=False)
    chat_allowed = models.BooleanField(default=False)
    appointment_allowed = models.BooleanField(default=False)
    ai_diet_allowed = models.BooleanField(default=False)
    BMI_Calculator_allowed = models.BooleanField(default=False)
    Fat_Calculator_allowed = models.BooleanField(default=False)
    expert_consults = models.PositiveIntegerField(
        default=0,
        verbose_name="Expert Consultations Count",
        help_text="Number of expert consultations included (0 = Unlimited)"
    )
    inhouse_consults = models.PositiveIntegerField(
        default=0,
        verbose_name="In-House Consultations Count",
        help_text="Number of in-house consultations included (0 = Unlimited)"
    )
    meal_log_allowed = models.BooleanField(default=False)
    water_intake_allowed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    inhouse_consultation_fee = models.PositiveIntegerField(
        default=200,
        help_text="Fee in rupees for single inhouse consultation"
    )
    expert_consultation_fee = models.PositiveIntegerField(
        default=500,
        help_text="Fee in rupees for single expert consultation"
    )

    # ── Nutritionist Practitioner Feature Flags ──────────────────────────────
    nutri_ai_diet_allowed = models.BooleanField(
        default=True,
        verbose_name="AI Assistant / Smart AI Diet Formulation",
        help_text="Allows AI-powered automated diet formulations for patients"
    )
    nutri_manual_diet_allowed = models.BooleanField(
        default=True,
        verbose_name="Manual Diet Formulation & Editing",
        help_text="Allows custom manual diet plan formulation & template editing"
    )
    nutri_bulk_upload_allowed = models.BooleanField(
        default=False,
        verbose_name="Bulk Patient Upload (CSV/Excel)",
        help_text="Allows batch importing patients via CSV/Excel template"
    )
    nutri_lab_reports_allowed = models.BooleanField(
        default=True,
        verbose_name="Lab Report Uploads & Biomarker Tracking",
        help_text="Allows uploading and analyzing patient lab tests and health reports"
    )
    nutri_chat_allowed = models.BooleanField(
        default=True,
        verbose_name="Direct Real-time Patient Messaging",
        help_text="Allows direct real-time chat with assigned patients"
    )
    nutri_smart_assistant_allowed = models.BooleanField(
        default=True,
        verbose_name="Smart Assistant (Nutro AI Calorie & Nutrition)",
        help_text="Allows access to Nutro Smart Calorie Assistant"
    )
    nutri_online_appointment_allowed = models.BooleanField(
        default=True,
        verbose_name="Online Video Appointments",
        help_text="Allows offering and accepting virtual video consultation appointments"
    )
    nutri_offline_appointment_allowed = models.BooleanField(
        default=True,
        verbose_name="Offline Clinic Appointments",
        help_text="Allows in-person clinic appointments and scheduling"
    )
    nutri_export_reports_allowed = models.BooleanField(
        default=False,
        verbose_name="Diet Chart PDF Export & Advanced Analytics",
        help_text="Allows generating PDF reports and advanced clinical analytics"
    )
    nutri_max_patients = models.PositiveIntegerField(
        default=25,
        verbose_name="Max Active Patients Capacity",
        help_text="Maximum number of active assigned patients allowed (0 = Unlimited)"
    )

    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"


class UserSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)

    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()

    remaining_expert = models.PositiveIntegerField(default=0)
    remaining_inhouse = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="one_active_subscription_per_user"
            )
        ]


class Payment(models.Model):
    # ── nullable so pre-registration orders work before user account exists ───
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    amount = models.PositiveIntegerField()

    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)

    # ── stores email for pre-registration payments ────────────────────────────
    pending_email = models.EmailField(blank=True, null=True)

    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)