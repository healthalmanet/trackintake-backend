# subscriptions/utils.py

from django.utils.timezone import now
from rest_framework.exceptions import PermissionDenied

def get_active_subscription(user):
    return (
        user.subscriptions
        .filter(
            is_active=True,
            end_date__gte=now().date(),
            plan__is_active=True
        )
        .select_related("plan")
        .first()
    )


def require_plan_feature(user, feature_flag):
    subscription = get_active_subscription(user)

    if not subscription:
        raise PermissionDenied("Please upgrade to a paid plan.")

    # 🚫 Block FREE plan
    if subscription.plan.price == 0:
        raise PermissionDenied("Please upgrade to a paid plan.")

    # 🚫 Feature not included in plan
    if not getattr(subscription.plan, feature_flag, False):
        raise PermissionDenied(
            f"This feature is not included in your {subscription.plan.name} plan."
        )

    return subscription
