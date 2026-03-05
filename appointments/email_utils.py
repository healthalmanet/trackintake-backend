# appointments/email_utils.py

from django.core.mail import send_mail
from django.conf import settings

def send_appointment_email(to_email, subject, message):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False,
    )
