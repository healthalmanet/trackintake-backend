# appointments/email_utils.py
import logging
from utils.resend_email import send_resend_email_async

logger = logging.getLogger(__name__)

def send_appointment_email(to_email, subject, message):
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
        <h3 style="color: #2e7d32;">📅 TrackIntake Appointment Notification</h3>
        <p style="white-space: pre-wrap; font-size: 14px; line-height: 1.6; color: #333;">{message}</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #888;">TrackIntake Appointments Team</p>
    </div>
    """
    return send_resend_email_async(
        to=to_email,
        subject=subject,
        html=html_body,
        text=message,
    )
