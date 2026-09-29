from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from datetime import datetime, timedelta
from .models import (
    AvailabilitySlot,
    Appointment,
    PendingRefundAppointment,
    PendingPayoutAppointment,
)
from .forms import AvailabilitySlotAdminForm
from nutritionist.models import NutritionistProfile
from user.models import User


# ======================================================
# Availability Slot Admin
# ======================================================
@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    form = AvailabilitySlotAdminForm

    list_display = (
        "id",
        "nutritionist",
        "date",
        "start_time",
        "end_time",
        "slot_type",
        "is_booked",
    )
    list_filter = ("nutritionist", "date", "slot_type", "is_booked")
    search_fields = ("nutritionist__email", "nutritionist__full_name")

    fieldsets = (
        ("Slot Details", {
            "fields": (
                "nutritionist",
                "date",
                ("start_time", "end_time"),
                "slot_type",
                "slot_duration",
                "is_booked",
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        duration = form.cleaned_data.get("slot_duration")

        if duration:
            start_dt = datetime.combine(obj.date, obj.start_time)
            end_dt = datetime.combine(obj.date, obj.end_time)
            slots_created = 0

            while start_dt + timedelta(minutes=duration) <= end_dt:
                AvailabilitySlot.objects.create(
                    nutritionist=obj.nutritionist,
                    date=obj.date,
                    start_time=start_dt.time(),
                    end_time=(start_dt + timedelta(minutes=duration)).time(),
                    slot_type=obj.slot_type or "BOTH",
                    is_booked=False,
                )
                start_dt += timedelta(minutes=duration)
                slots_created += 1

            messages.success(
                request,
                f"{slots_created} slots generated successfully."
            )
        else:
            super().save_model(request, obj, form, change)
            messages.success(request, "Slot saved successfully.")


# ======================================================
# Main Appointment Admin
# ======================================================
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient_display",
        "nutritionist_display",
        "session_schedule",
        "appointment_type_badge",
        "status_badge",
        "patient_payment_badge",
        "practitioner_payout_badge",
        "reschedule_count_display",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "payout_status",
        "appointment_type",
        "appointment_category",
        "cancelled_by",
        "slot_date",
        "created_at",
    )

    search_fields = (
        "id",
        "patient__email",
        "patient__full_name",
        "nutritionist__email",
        "nutritionist__full_name",
        "payout_transaction_ref",
    )

    readonly_fields = (
        "patient",
        "nutritionist",
        "slot",
        "slot_date",
        "slot_start_time",
        "slot_end_time",
        "appointment_category",
        "selected_expert",
        "created_at",
        "reschedule_count",
        "rescheduled_at",
        "cancelled_at",
    )

    fieldsets = (
        ("Session Information", {
            "fields": (
                ("patient", "nutritionist"),
                ("appointment_category", "appointment_type"),
                ("slot_date", "slot_start_time", "slot_end_time"),
                "status",
                "assigned_by",
                "meeting_link",
            )
        }),
        ("Cancellation & Rescheduling Details", {
            "fields": (
                ("cancelled_by", "cancelled_at"),
                "cancellation_reason",
                ("reschedule_count", "rescheduled_at"),
            )
        }),
        ("Patient Payment & Refund Management (Whom to Refund)", {
            "description": "Track consultation fees collected and manage refund status for cancellations.",
            "fields": (
                ("fee_amount", "payment_status"),
                ("refund_amount", "refunded_at"),
                "refund_notes",
            )
        }),
        ("Nutritionist Earnings & Payout Management (Whom to Pay)", {
            "description": "Manage practitioner earnings from online consultations and record payouts.",
            "fields": (
                ("payout_amount", "payout_status"),
                ("payout_marked_at", "payout_transaction_ref"),
            )
        }),
        ("Clinical Advice & Notes", {
            "classes": ("collapse",),
            "fields": ("notes", "instructions"),
        }),
    )

    actions = [
        "mark_refund_completed",
        "mark_payout_paid",
        "reopen_slot_for_appointment",
    ]

    def patient_display(self, obj):
        name = obj.patient.full_name or obj.patient.username
        return format_html(
            "<strong>{}</strong><br><span style='color: #64748b; font-size: 11px;'>{}</span>",
            name,
            obj.patient.email,
        )
    patient_display.short_description = "Patient"

    def nutritionist_display(self, obj):
        name = obj.nutritionist.full_name or obj.nutritionist.username
        return format_html(
            "<strong>{}</strong><br><span style='color: #64748b; font-size: 11px;'>{}</span>",
            name,
            obj.nutritionist.email,
        )
    nutritionist_display.short_description = "Practitioner"

    def session_schedule(self, obj):
        d = obj.slot_date or (obj.slot.date if obj.slot else None)
        st = obj.slot_start_time or (obj.slot.start_time if obj.slot else None)
        et = obj.slot_end_time or (obj.slot.end_time if obj.slot else None)
        if d and st:
            return format_html(
                "<strong>{}</strong><br><span style='color: #2563eb;'>{} - {}</span>",
                d.strftime("%d %b %Y"),
                st.strftime("%I:%M %p"),
                et.strftime("%I:%M %p") if et else "",
            )
        return "—"
    session_schedule.short_description = "Date & Time"

    def appointment_type_badge(self, obj):
        if obj.appointment_type == "VIRTUAL":
            return format_html("<span style='background-color: #dbeafe; color: #1d4ed8; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;'>Virtual Zoom</span>")
        return format_html("<span style='background-color: #dcfce7; color: #15803d; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;'>In-Clinic</span>")
    appointment_type_badge.short_description = "Mode"

    def status_badge(self, obj):
        if obj.status == "CONFIRMED":
            return format_html("<span style='background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;'>Confirmed</span>")
        actor = f" by {obj.cancelled_by}" if obj.cancelled_by else ""
        return format_html("<span style='background-color: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;'>Cancelled{}</span>", actor)
    status_badge.short_description = "Status"

    def patient_payment_badge(self, obj):
        st = obj.payment_status
        fee = obj.fee_amount
        if st == "PENDING_REFUND":
            return format_html(
                "<span style='background-color: #fef08a; color: #854d0e; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;'>⚠️ PENDING REFUND: ₹{}</span>",
                obj.refund_amount or fee,
            )
        elif st == "REFUNDED":
            return format_html(
                "<span style='background-color: #f1f5f9; color: #475569; padding: 3px 8px; border-radius: 6px; font-size: 11px;'>Refunded: ₹{}</span>",
                obj.refund_amount,
            )
        elif st == "PAID":
            return format_html("<span style='color: #16a34a; font-weight: bold; font-size: 12px;'>Paid ₹{}</span>", fee)
        elif st == "NO_REFUND":
            return format_html("<span style='color: #64748b; font-size: 11px;'>No Refund Applicable</span>")
        return format_html("<span style='color: #94a3b8; font-size: 11px;'>Unpaid (₹{})</span>", fee)
    patient_payment_badge.short_description = "Patient Payment / Refund"

    def practitioner_payout_badge(self, obj):
        st = obj.payout_status
        amt = obj.payout_amount
        if st == "PENDING":
            return format_html(
                "<span style='background-color: #fed7aa; color: #9a3412; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;'>Owed ₹{} (PENDING)</span>",
                amt,
            )
        elif st == "PAID":
            return format_html(
                "<span style='background-color: #bbf7d0; color: #166534; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;'>Paid Out ₹{}</span>",
                amt,
            )
        elif st == "CANCELLED":
            return format_html("<span style='color: #94a3b8; font-size: 11px;'>Cancelled</span>")
        return format_html("<span style='color: #cbd5e1; font-size: 11px;'>N/A</span>")
    practitioner_payout_badge.short_description = "Practitioner Payout"

    def reschedule_count_display(self, obj):
        if obj.reschedule_count > 0:
            return format_html("<span style='color: #2563eb; font-weight: bold;'>{} / 2</span>", obj.reschedule_count)
        return "0"
    reschedule_count_display.short_description = "Reschedules"

    # Admin Actions
    @admin.action(description="💰 Mark Selected User Refunds as COMPLETED (Refunded)")
    def mark_refund_completed(self, request, queryset):
        updated = queryset.filter(payment_status="PENDING_REFUND").update(
            payment_status="REFUNDED",
            refunded_at=timezone.now(),
        )
        self.message_user(
            request,
            f"Successfully marked {updated} appointments as REFUNDED to patient.",
            messages.SUCCESS,
        )

    @admin.action(description="💼 Mark Selected Practitioner Payouts as COMPLETED (Paid)")
    def mark_payout_paid(self, request, queryset):
        updated = queryset.filter(payout_status="PENDING").update(
            payout_status="PAID",
            payout_marked_at=timezone.now(),
        )
        self.message_user(
            request,
            f"Successfully marked {updated} practitioner payouts as PAID.",
            messages.SUCCESS,
        )

    @admin.action(description="🔓 Restore / Free Time Slot for Selected Appointments")
    def reopen_slot_for_appointment(self, request, queryset):
        count = 0
        for appt in queryset:
            if appt.slot and appt.slot.is_booked:
                appt.slot.is_booked = False
                appt.slot.save(update_fields=["is_booked"])
                count += 1
        self.message_user(
            request,
            f"Restored {count} slots to available status.",
            messages.SUCCESS,
        )


# ======================================================
# Dedicated Admin: Pending User Refunds
# ======================================================
@admin.register(PendingRefundAppointment)
class PendingRefundAppointmentAdmin(AppointmentAdmin):
    list_display = (
        "id",
        "patient_display",
        "refund_action_card",
        "nutritionist_display",
        "session_schedule",
        "cancellation_info",
        "created_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(payment_status="PENDING_REFUND")

    def refund_action_card(self, obj):
        amt = obj.refund_amount or obj.fee_amount
        return format_html(
            "<div style='background-color: #fef9c3; border: 1px solid #facc15; padding: 6px 12px; border-radius: 8px;'>"
            "<strong style='color: #854d0e; font-size: 13px;'>Refund Due: ₹{}</strong><br>"
            "<span style='color: #a16207; font-size: 11px;'>Patient: {} ({})</span>"
            "</div>",
            amt,
            obj.patient.full_name or obj.patient.username,
            obj.patient.email,
        )
    refund_action_card.short_description = "Whom to Refund & Amount"

    def cancellation_info(self, obj):
        actor = obj.cancelled_by or "Patient"
        reason = f"<br><i>Reason: {obj.cancellation_reason}</i>" if obj.cancellation_reason else ""
        return format_html(
            "Cancelled by: <strong>{}</strong> at {}{}",
            actor,
            obj.cancelled_at.strftime("%d %b %Y %H:%M") if obj.cancelled_at else "—",
            format_html(reason),
        )
    cancellation_info.short_description = "Cancellation Context"


# ======================================================
# Dedicated Admin: Pending Practitioner Payouts
# ======================================================
@admin.register(PendingPayoutAppointment)
class PendingPayoutAppointmentAdmin(AppointmentAdmin):
    list_display = (
        "id",
        "nutritionist_display",
        "payout_action_card",
        "patient_display",
        "session_schedule",
        "appointment_type_badge",
        "status_badge",
        "created_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(payout_status="PENDING")

    def payout_action_card(self, obj):
        amt = obj.payout_amount
        return format_html(
            "<div style='background-color: #ffedd5; border: 1px solid #fdba74; padding: 6px 12px; border-radius: 8px;'>"
            "<strong style='color: #9a3412; font-size: 13px;'>Payout Due: ₹{}</strong><br>"
            "<span style='color: #c2410c; font-size: 11px;'>Pay To: {} ({})</span>"
            "</div>",
            amt,
            obj.nutritionist.full_name or obj.nutritionist.username,
            obj.nutritionist.email,
        )
    payout_action_card.short_description = "Whom to Pay & Amount"
