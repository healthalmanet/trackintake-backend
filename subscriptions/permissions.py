from rest_framework.permissions import BasePermission
from django.utils import timezone
from .models import UserSubscription


def get_active_nutritionist_subscription(user):
    """
    Returns the active UserSubscription for a nutritionist, or None if expired/not found.
    """
    if not user or not user.is_authenticated:
        return None

    # Admin / superuser bypass
    if getattr(user, "is_admin", False) or getattr(user, "is_staff", False) or getattr(user, "role", "") == "admin":
        return "ADMIN_OVERRIDE"

    today = timezone.now().date()
    sub = (
        UserSubscription.objects
        .filter(
            user=user,
            is_active=True,
            plan__plan_type="nutritionist"
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )

    if not sub:
        return None

    if sub.end_date and sub.end_date < today:
        return None

    return sub


def check_nutritionist_feature(user, feature_name):
    """
    Checks if a nutritionist user is allowed to access a specific feature.
    Returns: (is_allowed: bool, message: str, plan_name: str)
    """
    # Admin / Staff override
    if getattr(user, "is_admin", False) or getattr(user, "is_staff", False) or getattr(user, "role", "") == "admin":
        return True, None, "Admin"

    sub = get_active_nutritionist_subscription(user)
    if not sub:
        return (
            False,
            "You do not have an active practitioner subscription. Please choose a plan to access clinical features.",
            "No Active Plan"
        )

    if sub == "ADMIN_OVERRIDE":
        return True, None, "Admin"

    is_allowed = getattr(sub.plan, feature_name, False)
    if not is_allowed:
        feature_labels = {
            "nutri_ai_diet_allowed": "AI Assistant / Smart AI Diet Formulation",
            "nutri_manual_diet_allowed": "Custom Manual Diet Formulations",
            "nutri_bulk_upload_allowed": "Bulk Patient CSV/Excel Upload",
            "nutri_lab_reports_allowed": "Lab Reports Tracking & Biomarker Analysis",
            "nutri_chat_allowed": "Direct Real-time Patient Messaging",
            "nutri_smart_assistant_allowed": "Nutro Smart Calorie Assistant",
            "nutri_online_appointment_allowed": "Online Video Appointments",
            "nutri_offline_appointment_allowed": "Offline Clinic Appointments",
            "nutri_export_reports_allowed": "Diet Chart PDF Export & Advanced Analytics",
        }
        human_name = feature_labels.get(feature_name, feature_name)
        return (
            False,
            f"Your current tier ({sub.plan.name}) does not support {human_name}. Upgrade your practitioner plan to unlock this feature.",
            sub.plan.name
        )

    return True, None, sub.plan.name


def check_nutritionist_patient_capacity(user):
    """
    Checks if nutritionist has reached their max active patient capacity limit.
    Returns: (can_add_more: bool, current_count: int, max_limit: int, message: str)
    """
    if getattr(user, "is_admin", False) or getattr(user, "is_staff", False) or getattr(user, "role", "") == "admin":
        return True, 0, 0, None

    sub = get_active_nutritionist_subscription(user)
    if not sub or sub == "ADMIN_OVERRIDE":
        return True, 0, 0, None

    max_patients = sub.plan.nutri_max_patients or 0
    if max_patients == 0:
        # Unlimited
        return True, 0, 0, None

    from nutritionist.models import PatientAssignment
    current_count = PatientAssignment.objects.filter(nutritionist=user).count()

    if current_count >= max_patients:
        return (
            False,
            current_count,
            max_patients,
            f"You have reached your maximum capacity limit of {max_patients} active patients on the {sub.plan.name} tier. Upgrade your plan to manage more patients."
        )

    return True, current_count, max_patients, None
