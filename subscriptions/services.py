from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import UserSubscription
from rest_framework.exceptions import PermissionDenied

from django.utils.timezone import now


def check_patient_ai_diet_access(patient):
    """
    HARD GATE: Allow AI diet generation ONLY if
    patient's active plan includes AI diet.
    """

    subscription = (
        UserSubscription.objects
        .filter(
            user=patient,
            is_active=True,
            end_date__gte=now().date()
        )
        .select_related("plan")
        .first()
    )

    if not subscription:
        raise PermissionDenied(
            "Patient does not have an active subscription."
        )

    if not subscription.plan.ai_diet_allowed:
        raise PermissionDenied(
            f"AI Diet is not included in the patient's "
            f"{subscription.plan.name} plan."
        )

    return subscription


@transaction.atomic
def consume_consultation(user, consult_type: str):
    """
    consult_type: 'expert' | 'inhouse'
    """

    subscription = (
        UserSubscription.objects
        .select_for_update()
        .filter(user=user, is_active=True)
        .first()
    )

    if not subscription:
        raise PermissionDenied("No active subscription found.")

    # 🔒 Expiry check
    if subscription.end_date < timezone.now().date():
        subscription.is_active = False
        subscription.save(update_fields=["is_active"])
        raise PermissionDenied("Subscription expired.")

    if consult_type == "expert":
        if subscription.remaining_expert <= 0:
            raise PermissionDenied("No expert consultations left.")
        subscription.remaining_expert -= 1

    elif consult_type == "inhouse":
        if subscription.remaining_inhouse <= 0:
            raise PermissionDenied("No in-house consultations left.")
        subscription.remaining_inhouse -= 1

    else:
        raise ValueError("Invalid consultation type.")

    subscription.save(
        update_fields=["remaining_expert", "remaining_inhouse"]
    )

    return subscription

@transaction.atomic
def activate_plan_for_user(user, plan):
    UserSubscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "start_date": timezone.now().date(),
            "end_date": timezone.now().date() + timedelta(days=plan.duration_days),
            "remaining_inhouse": plan.inhouse_consults,
            "remaining_expert": plan.expert_consults,
            "is_active": True,
        }
    )

