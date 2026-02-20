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
    nutritionist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
        db_index=True,
    )

    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    is_booked = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        indexes = [
            # Fast dashboard filtering
            models.Index(fields=["nutritionist", "is_booked"]),
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

    slot = models.OneToOneField(
        AvailabilitySlot,
        on_delete=models.CASCADE,
        related_name="appointment",
        db_index=True,
    )

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

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["nutritionist", "status"]),
            models.Index(fields=["patient", "created_at"]),
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
