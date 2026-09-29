# appointments/email_utils.py
import logging
from django.conf import settings
from utils.resend_email import send_resend_email_async

logger = logging.getLogger(__name__)

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "https://trackintake.co.in")


def format_time_str(t):
    if not t:
        return ""
    try:
        return t.strftime("%I:%M %p")
    except Exception:
        return str(t)


def format_date_str(d):
    if not d:
        return ""
    try:
        return d.strftime("%A, %d %B %Y")
    except Exception:
        return str(d)


def send_appointment_email(to_email, subject, message):
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
            <h2 style="color: #2e7d32; margin: 0; font-size: 20px;">📅 TrackIntake Consultation Update</h2>
        </div>
        <p style="white-space: pre-wrap; font-size: 14px; line-height: 1.6; color: #334155;">{message}</p>
        <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
        <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Health & Nutrition Team • <a href="{FRONTEND_URL}" style="color: #2e7d32; text-decoration: none;">trackintake.co.in</a></p>
    </div>
    """
    return send_resend_email_async(
        to=to_email,
        subject=subject,
        html=html_body,
        text=message,
    )


def send_booking_confirmation_emails(appointment):
    """
    Sends detailed appointment booking confirmation emails to BOTH patient and nutritionist.
    Includes date, time, participant name, mode, and Zoom link / clinic details.
    """
    patient = appointment.patient
    nutritionist = appointment.nutritionist
    slot = appointment.slot
    date_str = format_date_str(appointment.slot_date or (slot.date if slot else None))
    time_str = f"{format_time_str(appointment.slot_start_time or (slot.start_time if slot else None))} - {format_time_str(appointment.slot_end_time or (slot.end_time if slot else None))}"
    mode_label = "Virtual Video Consultation (Zoom)" if appointment.appointment_type == "VIRTUAL" else "In-Clinic Consultation"
    
    nutri_profile = getattr(nutritionist, "nutritionist_profile", None)
    offline_location = getattr(nutri_profile, "offline_location", "") or "Clinic location to be confirmed"
    meeting_link = appointment.meeting_link or "Zoom link will be active shortly prior to start."

    # 1. Email to Patient
    if patient and patient.email:
        patient_name = patient.full_name or patient.email
        nutri_name = nutritionist.full_name or nutritionist.email
        subject_patient = f"🎉 Consultation Confirmed with {nutri_name} on {date_str}"
        
        mode_section = f"""
        <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 0 0 8px 0; font-weight: bold; color: #166534;">🎥 Zoom Video Meeting Link:</p>
            <p style="margin: 0; font-family: monospace; font-size: 13px; word-break: break-all;">
                <a href="{meeting_link}" target="_blank" style="color: #2563eb; text-decoration: underline;">{meeting_link}</a>
            </p>
            <p style="margin: 8px 0 0 0; font-size: 12px; color: #15803d;">Click the link above at the scheduled time to join your session.</p>
        </div>
        """ if appointment.appointment_type == "VIRTUAL" else f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 0 0 4px 0; font-weight: bold; color: #334155;">📍 Clinic / Consultation Address:</p>
            <p style="margin: 0; font-size: 13px; color: #475569;">{offline_location}</p>
        </div>
        """

        html_patient = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #2e7d32; margin: 0; font-size: 20px;">✅ Appointment Confirmed!</h2>
            </div>
            <p style="font-size: 15px; color: #334155;">Hello <strong>{patient_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                Your appointment with <strong>{nutri_name}</strong> has been successfully booked. Here are your consultation details:
            </p>

            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b; width: 35%;"><strong>Date:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: bold;">{date_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Time Slot:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: bold;">{time_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Consultation Mode:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b;">{mode_label}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Nutritionist:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b;">{nutri_name}</td>
                </tr>
            </table>

            {mode_section}

            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin-top: 20px;">
                Need to reschedule? You can reschedule up to 2 times, provided you do so at least 24 hours prior to the appointment.
            </p>

            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Appointments • <a href="{FRONTEND_URL}/appointments" style="color: #2e7d32; text-decoration: none;">View Appointments</a></p>
        </div>
        """
        send_resend_email_async(
            to=patient.email,
            subject=subject_patient,
            html=html_patient,
            text=f"Appointment Confirmed with {nutri_name} on {date_str} at {time_str}. Mode: {mode_label}. Link: {meeting_link}",
        )

    # 2. Email to Nutritionist
    if nutritionist and nutritionist.email:
        nutri_name = nutritionist.full_name or nutritionist.email
        patient_name = patient.full_name or patient.email
        subject_nutri = f"🗓️ New Booking: {patient_name} on {date_str} ({time_str})"

        mode_section_nutri = f"""
        <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 0 0 8px 0; font-weight: bold; color: #166534;">🎥 Zoom Video Meeting Link (Host):</p>
            <p style="margin: 0; font-family: monospace; font-size: 13px; word-break: break-all;">
                <a href="{meeting_link}" target="_blank" style="color: #2563eb; text-decoration: underline;">{meeting_link}</a>
            </p>
        </div>
        """ if appointment.appointment_type == "VIRTUAL" else f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 0 0 4px 0; font-weight: bold; color: #334155;">📍 In-Clinic Session Location:</p>
            <p style="margin: 0; font-size: 13px; color: #475569;">{offline_location}</p>
        </div>
        """

        html_nutri = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #2e7d32; margin: 0; font-size: 20px;">🗓️ New Patient Booking</h2>
            </div>
            <p style="font-size: 15px; color: #334155;">Hello <strong>{nutri_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                A new appointment has been scheduled with patient <strong>{patient_name}</strong>.
            </p>

            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b; width: 35%;"><strong>Patient:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: bold;">{patient_name} ({patient.email})</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Date:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: bold;">{date_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Time Slot:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: bold;">{time_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Type:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b;">{mode_label}</td>
                </tr>
            </table>

            {mode_section_nutri}

            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Practitioner Portal • <a href="{FRONTEND_URL}/nutritionist/availability" style="color: #2e7d32; text-decoration: none;">View Availability & Bookings</a></p>
        </div>
        """
        send_resend_email_async(
            to=nutritionist.email,
            subject=subject_nutri,
            html=html_nutri,
            text=f"New booking with patient {patient_name} on {date_str} at {time_str}. Mode: {mode_label}. Link: {meeting_link}",
        )


def send_cancellation_emails(appointment, cancelled_by_role, reason=""):
    """
    Sends cancellation notification emails to BOTH patient and nutritionist.
    Explains the policy, who cancelled, slot status, and refund eligibility.
    """
    patient = appointment.patient
    nutritionist = appointment.nutritionist
    slot = appointment.slot
    date_str = format_date_str(appointment.slot_date or (slot.date if slot else None))
    time_str = f"{format_time_str(appointment.slot_start_time or (slot.start_time if slot else None))} - {format_time_str(appointment.slot_end_time or (slot.end_time if slot else None))}"
    
    actor = "Nutritionist" if cancelled_by_role == "NUTRITIONIST" else "Patient"
    
    # Refund notice calculation
    if appointment.payment_status == "PENDING_REFUND":
        refund_note = "Your refund request of ₹" + str(appointment.refund_amount) + " has been marked as PENDING and will be processed by Admin."
    elif appointment.payment_status == "NO_REFUND":
        if cancelled_by_role == "NUTRITIONIST":
            refund_note = "This session was cancelled by your practitioner. No upfront payment was required, so no refund is needed."
        else:
            refund_note = "As per platform policy, cancellations within 24 hours of appointment carry no refund."
    else:
        refund_note = "No refund is required for this session."

    subject = f"❌ Appointment Cancelled: Session on {date_str} ({time_str})"

    # Email to Patient
    if patient and patient.email:
        patient_name = patient.full_name or patient.email
        html_p = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #fee2e2; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #ef4444; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #ef4444; margin: 0; font-size: 20px;">❌ Appointment Cancelled</h2>
            </div>
            <p style="font-size: 15px; color: #334155;">Hello <strong>{patient_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                Your appointment scheduled for <strong>{date_str} at {time_str}</strong> has been cancelled by <strong>{actor}</strong>.
            </p>
            {f'<p style="font-size: 13px; color: #64748b; background-color: #f8fafc; padding: 10px; border-radius: 6px;"><strong>Reason:</strong> {reason}</p>' if reason else ''}
            
            <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 14px; margin: 16px 0;">
                <p style="margin: 0; font-weight: bold; color: #991b1b; font-size: 13px;">Refund Policy Notice:</p>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: #b91c1c;">{refund_note}</p>
            </div>

            <p style="font-size: 13px; color: #64748b; line-height: 1.5;">
                The time slot has been freed and made available again. You may visit TrackIntake to book another session at your convenience.
            </p>

            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Appointments • <a href="{FRONTEND_URL}/appointments" style="color: #2e7d32; text-decoration: none;">Book Another Appointment</a></p>
        </div>
        """
        send_resend_email_async(
            to=patient.email,
            subject=subject,
            html=html_p,
            text=f"Your appointment on {date_str} at {time_str} was cancelled by {actor}. {refund_note}",
        )

    # Email to Nutritionist
    if nutritionist and nutritionist.email:
        nutri_name = nutritionist.full_name or nutritionist.email
        html_n = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #fee2e2; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #ef4444; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #ef4444; margin: 0; font-size: 20px;">❌ Appointment Cancelled</h2>
            </div>
            <p style="font-size: 15px; color: #334155;">Hello <strong>{nutri_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                The appointment with patient <strong>{patient.full_name or patient.email}</strong> on <strong>{date_str} at {time_str}</strong> has been cancelled by <strong>{actor}</strong>.
            </p>
            {f'<p style="font-size: 13px; color: #64748b; background-color: #f8fafc; padding: 10px; border-radius: 6px;"><strong>Reason:</strong> {reason}</p>' if reason else ''}

            <p style="font-size: 13px; color: #166534; background-color: #f0fdf4; border: 1px solid #bbf7d0; padding: 12px; border-radius: 8px;">
                ✅ This availability slot ({date_str} {time_str}) has been restored to <strong>Available</strong> for new bookings.
            </p>

            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Practitioner Portal • <a href="{FRONTEND_URL}/nutritionist/availability" style="color: #2e7d32; text-decoration: none;">View Availability</a></p>
        </div>
        """
        send_resend_email_async(
            to=nutritionist.email,
            subject=subject,
            html=html_n,
            text=f"Appointment on {date_str} at {time_str} with {patient.full_name or patient.email} was cancelled by {actor}. Slot is now available again.",
        )


def send_reschedule_emails(appointment, rescheduled_by_role, old_slot_str, new_slot_str):
    """
    Sends reschedule notification emails to BOTH patient and nutritionist with old and new timings.
    """
    patient = appointment.patient
    nutritionist = appointment.nutritionist
    actor = "Nutritionist" if rescheduled_by_role == "NUTRITIONIST" else "Patient"
    meeting_link = appointment.meeting_link or "Link will be updated in portal."

    subject = f"🔄 Appointment Rescheduled: New Time on {new_slot_str}"

    # 1. Email to Patient
    if patient and patient.email:
        patient_name = patient.full_name or patient.email
        reschedule_remaining = 2 - appointment.reschedule_count
        html_p = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #2563eb; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #2563eb; margin: 0; font-size: 20px;">🔄 Appointment Rescheduled</h2>
            </div>
            <p style="font-size: 15px; color: #334155;">Hello <strong>{patient_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                Your appointment with <strong>{nutritionist.full_name or nutritionist.email}</strong> was rescheduled by <strong>{actor}</strong>.
            </p>

            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b; width: 35%;"><strong>Previous Time:</strong></td>
                    <td style="padding: 8px 0; color: #94a3b8; text-decoration: line-through;">{old_slot_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #16a34a; width: 35%;"><strong>NEW Scheduled Time:</strong></td>
                    <td style="padding: 8px 0; color: #15803d; font-weight: bold; font-size: 15px;">{new_slot_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b;"><strong>Mode:</strong></td>
                    <td style="padding: 8px 0; color: #1e293b;">{appointment.appointment_type}</td>
                </tr>
            </table>

            {f'<p style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px; font-size: 13px;"><strong>Video Meeting Link:</strong> <a href="{meeting_link}">{meeting_link}</a></p>' if appointment.appointment_type == "VIRTUAL" and meeting_link else ''}

            <p style="font-size: 12px; color: #64748b; margin-top: 16px;">
                Patient Reschedules Used: <strong>{appointment.reschedule_count}/2</strong> ({max(0, reschedule_remaining)} remaining).
            </p>

            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Appointments • <a href="{FRONTEND_URL}/appointments" style="color: #2e7d32; text-decoration: none;">View Appointments</a></p>
        </div>
        """
        send_resend_email_async(
            to=patient.email,
            subject=subject,
            html=html_p,
            text=f"Appointment rescheduled by {actor}. New time: {new_slot_str} (Previously: {old_slot_str}).",
        )

    # 2. Email to Nutritionist
    if nutritionist and nutritionist.email:
        nutri_name = nutritionist.full_name or nutritionist.email
        html_n = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <div style="border-bottom: 2px solid #2563eb; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #2563eb; margin: 0; font-size: 20px;">🔄 Appointment Rescheduled</h2>
            </div>
            <p style="font-size: 15px; color: #334155;">Hello <strong>{nutri_name}</strong>,</p>
            <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                The appointment with patient <strong>{patient.full_name or patient.email}</strong> was rescheduled by <strong>{actor}</strong>.
            </p>

            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #64748b; width: 35%;"><strong>Previous Time:</strong></td>
                    <td style="padding: 8px 0; color: #94a3b8; text-decoration: line-through;">{old_slot_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; color: #16a34a; width: 35%;"><strong>NEW Scheduled Time:</strong></td>
                    <td style="padding: 8px 0; color: #15803d; font-weight: bold; font-size: 15px;">{new_slot_str}</td>
                </tr>
            </table>

            {f'<p style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px; font-size: 13px;"><strong>Host Zoom Link:</strong> <a href="{meeting_link}">{meeting_link}</a></p>' if appointment.appointment_type == "VIRTUAL" and meeting_link else ''}

            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">TrackIntake Practitioner Portal • <a href="{FRONTEND_URL}/nutritionist/availability" style="color: #2e7d32; text-decoration: none;">View Schedule</a></p>
        </div>
        """
        send_resend_email_async(
            to=nutritionist.email,
            subject=subject,
            html=html_n,
            text=f"Appointment with {patient.full_name or patient.email} rescheduled by {actor}. New time: {new_slot_str} (Previously: {old_slot_str}).",
        )
