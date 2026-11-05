# appointments/notification_utils.py
import logging
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from utils.resend_email import send_resend_email_async
from .models import AppointmentNotification
from .email_utils import (
    format_date_str,
    format_time_str,
    send_booking_confirmation_emails,
    FRONTEND_URL
)

logger = logging.getLogger(__name__)


def create_and_send_appointment_notification(
    recipient,
    appointment,
    notification_type,
    title,
    message,
    email_subject=None,
    email_html=None,
    send_email=True
):
    """
    Unified notification engine:
    1. Persists InApp Notification in PostgreSQL (for bell icon unread fetching).
    2. Broadcasts live WebSocket event to `user_{recipient.id}` via Channels.
    3. Dispatches async Resend/Gmail email with styled HTML body.
    """
    if not recipient:
        return None

    # 1. Persist In-App Notification
    try:
        notif = AppointmentNotification.objects.create(
            recipient=recipient,
            appointment=appointment,
            notification_type=notification_type,
            title=title,
            message=message,
            is_read=False,
        )
    except Exception as e:
        logger.error(f"❌ Failed to persist AppointmentNotification: {e}")
        notif = None

    notif_id = notif.id if notif else int(timezone.now().timestamp() * 1000)
    iso_time = notif.created_at.isoformat() if notif else timezone.now().isoformat()

    # 2. Real-Time WebSocket Push via Channels
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{recipient.id}",
                {
                    "type": "send_appointment_notification",
                    "id": notif_id,
                    "notification_id": notif_id,
                    "title": title,
                    "text": message,
                    "message": message,
                    "appointment_id": appointment.id if appointment else None,
                    "appointment_status": appointment.status if appointment else None,
                    "notification_type": notification_type,
                    "timestamp": iso_time,
                    "is_read": False,
                }
            )
            logger.info(f"📡 WebSocket notification pushed to user_{recipient.id}: '{title}'")
    except Exception as ws_err:
        logger.warning(f"⚠️ WebSocket push failed for user_{recipient.id}: {ws_err}")

    # 3. Async Gmail / Resend Email
    if send_email and recipient.email:
        try:
            subj = email_subject or f"TrackIntake Update: {title}"
            body_html = email_html or f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
                <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
                    <h2 style="color: #2e7d32; margin: 0; font-size: 20px;">📅 TrackIntake Consultation Update</h2>
                </div>
                <h3 style="color: #0f172a; margin: 0 0 12px 0; font-size: 16px;">{title}</h3>
                <p style="font-size: 14px; line-height: 1.6; color: #334155;">{message}</p>
                <div style="margin: 24px 0;">
                    <a href="{FRONTEND_URL}/dashboard/appointments" style="display: inline-block; background-color: #2e7d32; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-size: 13px;">
                        Open Consultation Portal →
                    </a>
                </div>
                <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
                <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Health & Nutrition Team • <a href="{FRONTEND_URL}" style="color: #2e7d32; text-decoration: none;">trackintake.co.in</a></p>
            </div>
            """
            send_resend_email_async(
                to=recipient.email,
                subject=subj,
                html=body_html,
                text=message
            )
        except Exception as mail_err:
            logger.error(f"❌ Email sending error for {recipient.email}: {mail_err}")

    return notif


def notify_appointment_booked_or_confirmed(appointment):
    """
    Called when an appointment is booked:
    - If status is CONFIRMED (In-house or expert fixed): sends full Gmail confirmation + In-App WebSocket to both.
    - If status is PENDING_REVIEW (expert variable): sends Case Review alerts to both.
    """
    patient = appointment.patient
    nutritionist = appointment.nutritionist
    slot = appointment.slot
    slot_date = format_date_str(appointment.slot_date or (slot.date if slot else None))
    slot_time = f"{format_time_str(appointment.slot_start_time or (slot.start_time if slot else None))} - {format_time_str(appointment.slot_end_time or (slot.end_time if slot else None))}"
    patient_name = patient.full_name or patient.email if patient else "Patient"
    nutri_name = nutritionist.full_name or nutritionist.email if nutritionist else "Nutritionist"

    if appointment.status == "PENDING_REVIEW":
        # 1. Notify Nutritionist: New Case Intake
        title_nutri = "📋 New Medical Case Intake Request"
        msg_nutri = f"Patient {patient_name} submitted medical intake notes for {slot_date} at {slot_time}. Please review the case and set your tailored consultation fee."
        html_nutri = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #4338ca; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #4338ca; margin: 0; font-size: 20px;">📋 New Case Review Request</h2>
            </div>
            <p style="font-size: 14px; color: #334155;">Hello <strong>Dr. {nutri_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                A new patient, <strong>{patient_name}</strong>, has requested a consultation with you for <strong>{slot_date} ({slot_time})</strong> and submitted their medical intake details.
            </p>
            {f'<div style="background-color: #eef2ff; border: 1px solid #c7d2fe; border-radius: 8px; padding: 14px; margin: 16px 0; font-size: 13px; color: #312e81;"><strong>Patient Health Concern:</strong><br/><em>"{appointment.patient_case_summary}"</em></div>' if appointment.patient_case_summary else ''}
            <p style="font-size: 13px; color: #64748b;">
                Please log in to your practitioner dashboard to review their complete clinical profile and submit your consultation fee quote.
            </p>
            <div style="margin: 24px 0;">
                <a href="{FRONTEND_URL}/nutritionist/availability" style="display: inline-block; background-color: #4338ca; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 13px;">
                    Review Case & Quote Fee →
                </a>
            </div>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Clinical Network • <a href="{FRONTEND_URL}" style="color: #4338ca; text-decoration: none;">trackintake.co.in</a></p>
        </div>
        """
        create_and_send_appointment_notification(
            recipient=nutritionist,
            appointment=appointment,
            notification_type=AppointmentNotification.NotificationType.CASE_REQUESTED,
            title=title_nutri,
            message=msg_nutri,
            email_subject=f"📋 New Case Intake from {patient_name} — Fee Quote Required",
            email_html=html_nutri,
        )

        # 2. Notify Patient: Case Intake Submitted
        title_pat = "📋 Medical Case Submitted for Review"
        msg_pat = f"Your health concerns and intake details for {slot_date} have been sent to Dr. {nutri_name}. You will receive a notification and email once your fee quote is ready."
        create_and_send_appointment_notification(
            recipient=patient,
            appointment=appointment,
            notification_type=AppointmentNotification.NotificationType.CASE_REQUESTED,
            title=title_pat,
            message=msg_pat,
            email_subject=f"📋 Case Intake Submitted to Dr. {nutri_name}",
        )

    elif appointment.status == "CONFIRMED":
        # 1. Send detailed Gmail confirmation with Zoom meeting link & clinic address
        try:
            send_booking_confirmation_emails(appointment)
        except Exception as e:
            logger.error(f"⚠️ send_booking_confirmation_emails error: {e}")

        # 2. In-App Notification & WebSocket for Nutritionist
        create_and_send_appointment_notification(
            recipient=nutritionist,
            appointment=appointment,
            notification_type=AppointmentNotification.NotificationType.CONFIRMED,
            title="🎉 New Consultation Confirmed",
            message=f"Session with {patient_name} on {slot_date} at {slot_time} is confirmed.",
            send_email=False, # Already sent via send_booking_confirmation_emails
        )

        # 3. In-App Notification & WebSocket for Patient
        create_and_send_appointment_notification(
            recipient=patient,
            appointment=appointment,
            notification_type=AppointmentNotification.NotificationType.CONFIRMED,
            title="🎉 Consultation Confirmed",
            message=f"Your appointment with Dr. {nutri_name} on {slot_date} at {slot_time} is confirmed.",
            send_email=False, # Already sent via send_booking_confirmation_emails
        )


def notify_fee_quoted(appointment):
    """
    Called when an expert practitioner quotes the consultation price for a variable case.
    """
    patient = appointment.patient
    nutritionist = appointment.nutritionist
    nutri_name = nutritionist.full_name or nutritionist.email if nutritionist else "Nutritionist"
    slot_date = format_date_str(appointment.slot_date or (appointment.slot.date if appointment.slot else None))
    slot_time = f"{format_time_str(appointment.slot_start_time or (appointment.slot.start_time if appointment.slot else None))} - {format_time_str(appointment.slot_end_time or (appointment.slot.end_time if appointment.slot else None))}"
    fee = appointment.fee_amount

    title = "💳 Consultation Fee Quote Ready"
    msg = f"Dr. {nutri_name} reviewed your case and quoted ₹{fee} for your session on {slot_date} ({slot_time}). Please review the credentials and confirm payment."

    html_patient = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <div style="border-bottom: 2px solid #ea580c; padding-bottom: 12px; margin-bottom: 20px;">
            <h2 style="color: #ea580c; margin: 0; font-size: 20px;">💳 Consultation Quote Ready</h2>
        </div>
        <p style="font-size: 14px; color: #334155;">Hello <strong>{patient.full_name or 'Patient'}</strong>,</p>
        <p style="font-size: 14px; line-height: 1.6; color: #475569;">
            <strong>Dr. {nutri_name}</strong> has reviewed your medical background and health goals for <strong>{slot_date} ({slot_time})</strong> and provided your tailored consultation fee quote:
        </p>

        <div style="background-color: #fff7ed; border: 1px solid #ffedd5; border-radius: 8px; padding: 16px; margin: 16px 0; text-align: center;">
            <span style="font-size: 13px; color: #9a3412; font-weight: bold; text-transform: uppercase;">Quoted Fee</span>
            <div style="font-size: 28px; font-weight: 900; color: #ea580c; margin-top: 4px;">₹{fee}</div>
            {f'<p style="margin: 8px 0 0 0; font-size: 13px; color: #7c2d12;">Note from Dr. {nutri_name}: "{appointment.nutritionist_quote_note}"</p>' if appointment.nutritionist_quote_note else ''}
        </div>

        <p style="font-size: 13px; color: #64748b;">
            To confirm this appointment and secure your slot, please log in to review the doctor's credentials and complete the payment.
        </p>

        <div style="margin: 24px 0;">
            <a href="{FRONTEND_URL}/dashboard/appointments" style="display: inline-block; background-color: #ea580c; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 13px;">
                Review Quote & Pay Online →
            </a>
        </div>
        <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
        <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Health & Nutrition Team • <a href="{FRONTEND_URL}" style="color: #ea580c; text-decoration: none;">trackintake.co.in</a></p>
    </div>
    """

    create_and_send_appointment_notification(
        recipient=patient,
        appointment=appointment,
        notification_type=AppointmentNotification.NotificationType.FEE_QUOTED,
        title=title,
        message=msg,
        email_subject=f"💳 Dr. {nutri_name} has quoted ₹{fee} for your consultation",
        email_html=html_patient,
    )


def notify_case_declined(appointment):
    """
    Called when an expert declines a case intake request.
    """
    patient = appointment.patient
    nutritionist = appointment.nutritionist
    nutri_name = nutritionist.full_name or nutritionist.email if nutritionist else "Nutritionist"
    reason = appointment.cancellation_reason or "Conditions outside practitioner clinical scope"

    title = "Case Request Update"
    msg = f"Dr. {nutri_name} was unable to accept your consultation case: '{reason}'. Your availability slot has been released."

    create_and_send_appointment_notification(
        recipient=patient,
        appointment=appointment,
        notification_type=AppointmentNotification.NotificationType.DECLINED,
        title=title,
        message=msg,
        email_subject=f"Case Request Update from Dr. {nutri_name}",
    )


def notify_appointment_cancelled(appointment, cancelled_by="PATIENT", reason=""):
    """
    Called when an appointment is cancelled by either the patient or nutritionist.
    Creates In-App notification & sends WebSocket push to the counterparty.
    """
    slot_date = format_date_str(appointment.slot_date or (appointment.slot.date if appointment.slot else None))
    slot_time = f"{format_time_str(appointment.slot_start_time or (appointment.slot.start_time if appointment.slot else None))} - {format_time_str(appointment.slot_end_time or (appointment.slot.end_time if appointment.slot else None))}"

    if cancelled_by == "PATIENT":
        recipient = appointment.nutritionist
        patient_name = appointment.patient.full_name or appointment.patient.email if appointment.patient else "Patient"
        title = "❌ Appointment Cancelled"
        msg = f"Patient {patient_name} cancelled the appointment scheduled for {slot_date} ({slot_time})."
        if reason:
            msg += f" Reason: {reason}"
    else:
        recipient = appointment.patient
        nutri_name = appointment.nutritionist.full_name or appointment.nutritionist.email if appointment.nutritionist else "Nutritionist"
        title = "❌ Appointment Cancelled"
        msg = f"Dr. {nutri_name} cancelled your appointment scheduled for {slot_date} ({slot_time})."
        if reason:
            msg += f" Reason: {reason}"

    create_and_send_appointment_notification(
        recipient=recipient,
        appointment=appointment,
        notification_type=AppointmentNotification.NotificationType.CANCELLED,
        title=title,
        message=msg,
        send_email=False, # Email is already sent via send_cancellation_emails
    )


def notify_appointment_rescheduled(appointment, rescheduled_by_role="PATIENT", new_slot_str=""):
    """
    Called when an appointment is rescheduled.
    Creates In-App notification & sends WebSocket push to the counterparty.
    """
    if rescheduled_by_role == "PATIENT":
        recipient = appointment.nutritionist
        patient_name = appointment.patient.full_name or appointment.patient.email if appointment.patient else "Patient"
        title = "🔄 Appointment Rescheduled"
        msg = f"Patient {patient_name} rescheduled the appointment to {new_slot_str}."
    else:
        recipient = appointment.patient
        nutri_name = appointment.nutritionist.full_name or appointment.nutritionist.email if appointment.nutritionist else "Nutritionist"
        title = "🔄 Appointment Rescheduled"
        msg = f"Dr. {nutri_name} rescheduled your appointment to {new_slot_str}."

    create_and_send_appointment_notification(
        recipient=recipient,
        appointment=appointment,
        notification_type=AppointmentNotification.NotificationType.CONFIRMED,
        title=title,
        message=msg,
        send_email=False, # Email is already sent via send_reschedule_emails
    )

