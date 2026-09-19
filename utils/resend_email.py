import os
import logging
import threading
import resend
from django.conf import settings

logger = logging.getLogger(__name__)

def _get_api_key():
    return getattr(settings, 'EMAIL_HOST_PASSWORD', None) or os.getenv('RESEND_API_KEY')

def send_resend_email(to, subject, html=None, text=None, from_email=None):
    """
    Safe, unified Resend-based email sender using the official Resend API.
    Works reliably on Render, cloud hosting, and local development.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning(f"⚠️ RESEND_API_KEY is not configured. Skipping email to {to}.")
        return None

    resend.api_key = api_key
    sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', "TrackEats <no-reply@trackintake.co.in>")
    recipient = [to] if isinstance(to, str) else to

    payload = {
        "from": sender,
        "to": recipient,
        "subject": subject,
    }

    if html:
        payload["html"] = html
    if text:
        payload["text"] = text
    if not html and not text:
        payload["text"] = subject

    try:
        response = resend.Emails.send(payload)
        logger.info(f"📧 Resend email sent successfully to {recipient} with subject: '{subject}'")
        return response
    except Exception as e:
        logger.error(f"❌ Resend email failed to {recipient}: {e}")
        return None

def send_resend_email_async(to, subject, html=None, text=None, from_email=None):
    """
    Sends Resend email asynchronously in a background daemon thread
    so ASGI/HTTP request-response cycles return instantly without blocking.
    """
    thread = threading.Thread(
        target=send_resend_email,
        args=(to, subject, html, text, from_email),
        daemon=True
    )
    thread.start()
    return thread