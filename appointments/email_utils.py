# appointments/email_utils.py
import logging
import threading
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

def _send_mail_worker(subject, message, to_email):
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=True,
        )
        logger.info(f"📧 Appointment email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"❌ Failed to send appointment email to {to_email}: {e}")

def send_appointment_email(to_email, subject, message):
    thread = threading.Thread(
        target=_send_mail_worker,
        args=(subject, message, to_email),
        daemon=True
    )
    thread.start()
