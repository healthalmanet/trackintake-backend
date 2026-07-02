# subscriptions/utils.py

import requests
import logging
from django.conf import settings
from django.utils.timezone import now
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def check_pathyatech_subscription(email):
    """
    Queries PathyaTech backend to verify if the patient has an active paid subscription
    and retrieves their plan's allowed feature gates.
    """
    if not email:
        return {"has_active_plan": False}
        
    url = f"{settings.PATHYATECH_BACKEND_URL.rstrip('/')}/api/subscriptions/patient-active/"
    headers = {
        "Authorization": f"Bearer {settings.PATHYATECH_API_SECRET}"
    }
    params = {
        "email": email
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"PathyaTech active check returned status code {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to query PathyaTech subscription status for {email}: {e}")
        
    return {"has_active_plan": False}


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
    # 1. Try local TrackIntake active subscription
    subscription = get_active_subscription(user)

    # 2. Check PathyaTech active paid plan if no local active plan or if local is free
    if not subscription or subscription.plan.price == 0:
        pt_status = check_pathyatech_subscription(user.email)
        if pt_status.get("has_active_plan"):
            plan_features = pt_status.get("plan", {}).get("features", {})
            if plan_features.get(feature_flag, False):
                return None  # Allowed, caller does not use return value
            else:
                raise PermissionDenied(
                    f"This feature is not included in your PathyaTech plan."
                )

    # 3. Standard local checks if not handled by PathyaTech
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

