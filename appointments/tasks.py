# appointments/tasks.py

from celery import shared_task
from django.utils import timezone
from .models import AppointmentReminder
from .email_utils import send_appointment_email

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def send_appointment_reminders(self):
    now = timezone.now()

    reminders = AppointmentReminder.objects.filter(
        remind_at__lte=now,
        is_sent=False
    ).select_related(
        "appointment",
        "appointment__patient",
        "appointment__nutritionist",
        "appointment__slot"
    )

    for reminder in reminders:
        appointment = reminder.appointment
        patient = appointment.patient
        slot = appointment.slot

        subject = "⏰ Appointment Reminder"
        message = f"""
Hello {patient.full_name},

This is a reminder that you have an appointment with
Nutritionist: {appointment.nutritionist.full_name}

📅 Date: {slot.date}
⏰ Time: {slot.start_time} – {slot.end_time}
⏳ Reminder: {reminder.reminder_type} before

Please be available on time.

– TrackEats Team
"""

        send_appointment_email(
            to_email=patient.email,
            subject=subject,
            message=message
        )

        reminder.is_sent = True
        reminder.save()
