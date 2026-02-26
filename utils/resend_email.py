import resend
from django.conf import settings

resend.api_key = settings.EMAIL_HOST_PASSWORD

def send_resend_email(to, subject, html):
    """
    Safe, Resend-based email sender.
    Works on Render without blocking the ASGI worker.
    """
    return resend.Emails.send({
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    })