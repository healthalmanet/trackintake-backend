
# from django.db import models
# from django.conf import settings
# from django.core.exceptions import ValidationError
# from nutritionist.models import NutritionistProfile

# class AvailabilitySlot(models.Model):
#     nutritionist = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="availability_slots"
#     )
#     date = models.DateField()
#     start_time = models.TimeField()
#     end_time = models.TimeField()
#     is_booked = models.BooleanField(default=False)
#     def clean(self):
#         overlapping_slots = AvailabilitySlot.objects.filter(
#             nutritionist=self.nutritionist,
#             date=self.date,
#             start_time__lt=self.end_time,
#             end_time__gt=self.start_time,
#         ).exclude(pk=self.pk)

#         if overlapping_slots.exists():
#             raise ValidationError(
#                 "This availability slot overlaps with an existing slot."
#             )

#     def save(self, *args, **kwargs):
#         # Ensure clean() is always called (Admin + API + Shell)
#         self.full_clean()
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.nutritionist} | {self.date} {self.start_time}-{self.end_time}"


# class Appointment(models.Model):

#     APPOINTMENT_CATEGORY = (
#         ('IN_HOUSE', 'In House'),
#         ('EXPERT', 'Expert'),
#     )

#     APPOINTMENT_TYPE = (
#         ('IN_PERSON', 'In Person'),
#         ('VIRTUAL', 'Virtual'),
#     )

#     STATUS = (
#         ('CONFIRMED', 'Confirmed'),
#         ('CANCELLED', 'Cancelled'),
#     )

#     ASSIGNED_BY = (
#         ('SYSTEM', 'System'),
#         ('USER', 'User'),
#         ('ADMIN', 'Admin'),
#     )

#     patient = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="appointments"
#     )

#     # 👉 User selected expert (ONLY for EXPERT flow)
#     selected_expert = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="expert_selected_appointments"
#     )

#     # 👉 Currently assigned nutritionist (admin can change)
#     nutritionist = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="nutritionist_appointments"
#     )

#     slot = models.OneToOneField(
#         AvailabilitySlot,
#         on_delete=models.CASCADE
#     )

#     appointment_category = models.CharField(
#         max_length=20,
#         choices=APPOINTMENT_CATEGORY
#     )

#     appointment_type = models.CharField(
#         max_length=20,
#         choices=APPOINTMENT_TYPE
#     )

#     assigned_by = models.CharField(
#         max_length=10,
#         choices=ASSIGNED_BY
#     )

#     meeting_link = models.URLField(blank=True, null=True)
#     status = models.CharField(max_length=20, choices=STATUS, default='CONFIRMED')
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.patient} → {self.nutritionist} ({self.appointment_category})"
#     def clean(self):
#         # EXPERT appointment
#         if self.appointment_category == "EXPERT":
#             if not self.selected_expert:
#                 raise ValidationError("Expert selection is required.")

#             try:
#                 profile = self.selected_expert.nutritionist_profile
#             except NutritionistProfile.DoesNotExist:
#                 raise ValidationError("Selected user is not a nutritionist.")

#             if profile.nutritionist_type != NutritionistProfile.NutritionistType.EXPERT:
#                 raise ValidationError("Only EXPERT nutritionists can be selected.")

#         # IN_HOUSE appointment
#         if self.appointment_category == "IN_HOUSE" and self.selected_expert:
#             raise ValidationError("Expert not allowed for in-house appointment.")

# # appointments/models.py

# class AppointmentReminder(models.Model):
#     REMINDER_TYPE = (
#         ("24H", "24 Hours"),
#         ("2H", "2 Hours"),
#     )

#     appointment = models.ForeignKey(
#         Appointment,
#         on_delete=models.CASCADE,
#         related_name="email_reminders"
#     )
#     remind_at = models.DateTimeField()
#     reminder_type = models.CharField(max_length=5, choices=REMINDER_TYPE)
#     is_sent = models.BooleanField(default=False)

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.reminder_type} reminder for appointment {self.appointment.id}"
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from nutritionist.models import NutritionistProfile


# ======================================================
# Availability Slot
# ======================================================
class AvailabilitySlot(models.Model):
    SLOT_TYPE = (
        ("VIRTUAL", "Virtual"),
        ("IN_PERSON", "In-Clinic"),
        ("BOTH", "Both (Virtual & In-Clinic)"),
    )

    nutritionist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
        db_index=True,
    )

    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_type = models.CharField(
        max_length=20,
        choices=SLOT_TYPE,
        default="BOTH",
        db_index=True,
    )

    is_booked = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        indexes = [
            # Fast dashboard filtering
            models.Index(fields=["nutritionist", "is_booked"]),
            models.Index(fields=["nutritionist", "slot_type"]),
            models.Index(fields=["nutritionist", "-date", "-start_time"]),
            # Overlap validation optimization
            models.Index(fields=["nutritionist", "date"]),
        ]

    def clean(self):
        """
        Prevent overlapping slots for the same nutritionist & date.
        """
        overlapping_slots = AvailabilitySlot.objects.filter(
            nutritionist=self.nutritionist,
            date=self.date,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)

        if overlapping_slots.exists():
            raise ValidationError(
                "This availability slot overlaps with an existing slot."
            )

    def save(self, *args, **kwargs):
        # Always enforce validation on writes
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.nutritionist} | "
            f"{self.date} {self.start_time}-{self.end_time}"
        )

    @property
    def appointment(self):
        """
        Returns the active confirmed appointment for this slot (or the most recent).
        Backwards compatible with slot.appointment usage across the codebase.
        """
        if hasattr(self, "_prefetched_objects_cache") and "appointments" in self._prefetched_objects_cache:
            confirmed = [a for a in self.appointments.all() if a.status == "CONFIRMED"]
            if confirmed:
                return confirmed[0]
            all_appts = list(self.appointments.all())
            return all_appts[0] if all_appts else None
        return self.appointments.filter(status="CONFIRMED").first() or self.appointments.first()


# ======================================================
# Appointment
# ======================================================
class Appointment(models.Model):

    APPOINTMENT_CATEGORY = (
        ("IN_HOUSE", "In House"),
        ("EXPERT", "Expert"),
    )

    APPOINTMENT_TYPE = (
        ("IN_PERSON", "In Person"),
        ("VIRTUAL", "Virtual"),
    )

    STATUS = (
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
    )

    ASSIGNED_BY = (
        ("SYSTEM", "System"),
        ("USER", "User"),
        ("ADMIN", "Admin"),
    )

    CANCELLED_BY = (
        ("PATIENT", "Patient"),
        ("NUTRITIONIST", "Nutritionist"),
        ("ADMIN", "Admin"),
    )

    PAYMENT_STATUS = (
        ("UNPAID", "Unpaid / Pay at Clinic"),
        ("PAID", "Paid Online"),
        ("PENDING_REFUND", "Pending Refund"),
        ("REFUNDED", "Refunded"),
        ("NO_REFUND", "No Refund Applicable"),
    )

    PAYOUT_STATUS = (
        ("PENDING", "Pending Admin Payout"),
        ("PAID", "Paid Out to Nutritionist"),
        ("CANCELLED", "Cancelled (No Payout)"),
        ("NOT_APPLICABLE", "Not Applicable"),
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
        db_index=True,
    )

    # Selected expert (ONLY for EXPERT category)
    selected_expert = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expert_selected_appointments",
        db_index=True,
    )

    # Currently assigned nutritionist
    nutritionist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nutritionist_appointments",
        db_index=True,
    )

    slot = models.ForeignKey(
        AvailabilitySlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        db_index=True,
    )

    # Cached slot timing for historical integrity after cancellation / rebooking
    slot_date = models.DateField(null=True, blank=True, db_index=True)
    slot_start_time = models.TimeField(null=True, blank=True)
    slot_end_time = models.TimeField(null=True, blank=True)

    appointment_category = models.CharField(
        max_length=20,
        choices=APPOINTMENT_CATEGORY,
        db_index=True,
    )

    appointment_type = models.CharField(
        max_length=20,
        choices=APPOINTMENT_TYPE,
    )

    assigned_by = models.CharField(
        max_length=10,
        choices=ASSIGNED_BY,
    )

    meeting_link = models.URLField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="CONFIRMED",
        db_index=True,
    )

    # 📝 Clinical notes / observations and dietary advice given by nutritionist
    notes = models.TextField(blank=True, default="")
    instructions = models.TextField(blank=True, default="")

    # ❌ Cancellation & Refund tracking
    cancelled_by = models.CharField(
        max_length=20,
        choices=CANCELLED_BY,
        null=True,
        blank=True,
        db_index=True,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, default="")

    # 🔄 Rescheduling tracking (patient capped at 2, nutritionist unlimited)
    reschedule_count = models.PositiveIntegerField(default=0)
    rescheduled_at = models.DateTimeField(null=True, blank=True)

    # 💰 Payment & Refund Status (Admin Managed)
    fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Consultation fee received by platform",
    )
    payment_status = models.CharField(
        max_length=25,
        choices=PAYMENT_STATUS,
        default="UNPAID",
        db_index=True,
    )
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Amount to be refunded to patient if eligible",
    )
    refund_notes = models.TextField(blank=True, default="")
    refunded_at = models.DateTimeField(null=True, blank=True)

    # 💼 Nutritionist Earnings & Payout Status (Admin Managed)
    payout_status = models.CharField(
        max_length=25,
        choices=PAYOUT_STATUS,
        default="NOT_APPLICABLE",
        db_index=True,
    )
    payout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Net payout owed/transferred to nutritionist",
    )
    payout_marked_at = models.DateTimeField(null=True, blank=True)
    payout_transaction_ref = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Admin transaction reference for payout disbursement",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["nutritionist", "status"]),
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["payment_status", "payout_status"]),
        ]

    def clean(self):
        """
        Business rules validation
        """
        # EXPERT appointment rules
        if self.appointment_category == "EXPERT":
            if not self.selected_expert:
                raise ValidationError("Expert selection is required.")

            try:
                profile = self.selected_expert.nutritionist_profile
            except NutritionistProfile.DoesNotExist:
                raise ValidationError("Selected user is not a nutritionist.")

            if (
                profile.nutritionist_type
                != NutritionistProfile.NutritionistType.EXPERT
            ):
                raise ValidationError(
                    "Only EXPERT nutritionists can be selected."
                )

        # IN_HOUSE rules
        if self.appointment_category == "IN_HOUSE" and self.selected_expert:
            raise ValidationError(
                "Expert not allowed for in-house appointment."
            )

    def __str__(self):
        return (
            f"{self.patient} → "
            f"{self.nutritionist} "
            f"({self.appointment_category})"
        )


# ======================================================
# Appointment Reminder
# ======================================================
class AppointmentReminder(models.Model):

    REMINDER_TYPE = (
        ("24H", "24 Hours"),
        ("2H", "2 Hours"),
    )

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="email_reminders",
        db_index=True,
    )

    remind_at = models.DateTimeField(db_index=True)
    reminder_type = models.CharField(
        max_length=5,
        choices=REMINDER_TYPE,
    )

    is_sent = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_sent", "remind_at"]),
        ]

    def __str__(self):
        return (
            f"{self.reminder_type} reminder "
            f"for appointment {self.appointment.id}"
        )
class AppointmentFeedback(models.Model):

    ROLE_CHOICES = (
        ("PATIENT", "Patient"),
        ("NUTRITIONIST", "Nutritionist"),
    )

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="feedbacks"
    )

    given_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    rating = models.IntegerField()  # 1–5
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("appointment", "given_by")  # one feedback per user

    def __str__(self):
        return f"{self.role} feedback for appointment {self.appointment.id}"


# ======================================================
# Admin Proxy Models for Direct Financial Management
# ======================================================
class PendingRefundManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(payment_status="PENDING_REFUND")


class PendingRefundAppointment(Appointment):
    objects = PendingRefundManager()

    class Meta:
        proxy = True
        verbose_name = "Pending User Refund"
        verbose_name_plural = "Pending User Refunds (Whom to Refund)"


class PendingPayoutManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(payout_status="PENDING")


class PendingPayoutAppointment(Appointment):
    objects = PendingPayoutManager()

    class Meta:
        proxy = True
        verbose_name = "Pending Practitioner Payout"
        verbose_name_plural = "Pending Practitioner Payouts (Whom to Pay)"