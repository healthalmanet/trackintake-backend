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
    and retrieves their plan's allowed feature gates. Uses Django cache to prevent slowness.
    """
    if not email:
        return {"has_active_plan": False}
        
    from django.core.cache import cache
    cache_key = f"pathyatech_sub_{email}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.PATHYATECH_BACKEND_URL.rstrip('/')}/api/subscriptions/patient-active/"
    headers = {
        "Authorization": f"Bearer {settings.PATHYATECH_API_SECRET}"
    }
    params = {
        "email": email
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=3)
        if response.status_code == 200:
            res_data = response.json()
            cache.set(cache_key, res_data, timeout=120)  # cache for 2 minutes
            return res_data
        else:
            logger.error(f"PathyaTech active check returned status code {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to query PathyaTech subscription status for {email}: {e}")
        
    fallback = {"has_active_plan": False}
    cache.set(cache_key, fallback, timeout=30)  # cache negative response briefly to prevent log spam/slowness
    return fallback


def get_active_subscription(user):
    """
    Retrieves the user's active subscription, automatically deactivating any expired subscriptions.
    """
    now_date = now().date()
    # Proactively mark expired subscriptions as inactive
    user.subscriptions.filter(
        is_active=True,
        end_date__lt=now_date
    ).update(is_active=False)

    return (
        user.subscriptions
        .filter(
            is_active=True,
            end_date__gte=now_date,
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
        has_expired = user.subscriptions.filter(end_date__lt=now().date()).exists()
        if has_expired:
            raise PermissionDenied("Your subscription has expired. Please renew your plan.")
        raise PermissionDenied("Please upgrade to a paid plan.")

    # 🚫 Block FREE plan
    if subscription.plan.price == 0:
        raise PermissionDenied("Please upgrade to a paid plan.")

    # 🚫 Feature not included in plan
    has_feature = getattr(subscription.plan, feature_flag, False)
    if not has_feature and getattr(subscription.plan, "plan_type", None) == "nutritionist":
        has_feature = getattr(subscription.plan, f"nutri_{feature_flag}", False)

    if not has_feature:
        raise PermissionDenied(
            f"This feature is not included in your {subscription.plan.name} plan."
        )

    return subscription


def get_razorpay_clients():
    """
    Returns a list of initialized Razorpay Client instances (primary first, then fallback/live if configured).
    """
    import razorpay
    clients = []
    seen_keys = set()

    # 1. Primary
    p_key = getattr(settings, "RAZORPAY_KEY_ID", None)
    p_sec = getattr(settings, "RAZORPAY_KEY_SECRET", None)
    if p_key and p_sec:
        try:
            clients.append(razorpay.Client(auth=(p_key, p_sec)))
            seen_keys.add(p_key)
        except Exception as e:
            logger.warning(f"Could not initialize primary Razorpay client: {e}")

    # 2. Fallback / Live
    l_key = getattr(settings, "RAZORPAY_LIVE_KEY_ID", None)
    l_sec = getattr(settings, "RAZORPAY_LIVE_KEY_SECRET", None)
    if l_key and l_sec and l_key not in seen_keys:
        try:
            clients.append(razorpay.Client(auth=(l_key, l_sec)))
        except Exception as e:
            logger.warning(f"Could not initialize fallback Razorpay client: {e}")

    return clients


def verify_razorpay_payment_signature(order_id, payment_id, signature):
    """
    Verifies Razorpay payment signature against primary secret, with fallback to live secret.
    """
    import hmac, hashlib
    msg = f"{order_id}|{payment_id}".encode()
    secrets = [
        getattr(settings, "RAZORPAY_KEY_SECRET", None),
        getattr(settings, "RAZORPAY_LIVE_KEY_SECRET", None),
    ]
    for sec in secrets:
        if not sec:
            continue
        try:
            expected = hmac.new(sec.encode(), msg, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, signature):
                return True
        except Exception:
            continue
    return False


def verify_razorpay_webhook_signature(payload, received_signature):
    """
    Verifies Razorpay webhook signature against primary secret, with fallback to live secret.
    """
    import hmac, hashlib
    if isinstance(payload, str):
        payload = payload.encode()
    secrets = [
        getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None),
        getattr(settings, "RAZORPAY_LIVE_WEBHOOK_SECRET", None),
    ]
    for sec in secrets:
        if not sec:
            continue
        try:
            expected = hmac.new(sec.encode(), payload, hashlib.sha256).hexdigest()
            if hmac.compare_digest(received_signature, expected):
                return True
        except Exception:
            continue
    return False


def reconcile_pending_payment(payment):
    """
    Checks Razorpay API to see if a pending payment order has already been paid/captured.
    If paid, updates payment status to 'success', saves payment_id, and activates the plan or consultation quota.
    """
    if not payment or payment.status == "success" or not payment.razorpay_order_id:
        return False

    clients = get_razorpay_clients()
    for client in clients:
        try:
            rzp_order = client.order.fetch(payment.razorpay_order_id)
            if not rzp_order:
                continue

            order_status = rzp_order.get("status")
            if order_status == "paid":
                # Fetch payments for this order
                rzp_payments = client.order.payments(payment.razorpay_order_id)
                items = rzp_payments.get("items", []) if isinstance(rzp_payments, dict) else []

                captured_payment = None
                for itm in items:
                    if itm.get("status") == "captured":
                        captured_payment = itm
                        break

                captured_id = captured_payment["id"] if captured_payment else (items[0]["id"] if items else None)

                payment.status = "success"
                if captured_id:
                    payment.razorpay_payment_id = captured_id
                payment.save(update_fields=["status", "razorpay_payment_id"])

                # Handle plan activation or consultation fee
                notes = (captured_payment.get("notes") if captured_payment else None) or rzp_order.get("notes") or {}
                consult_type = notes.get("consult_type")
                is_consult = (payment.payment_type == "consultation_fee") or (notes.get("type") == "consultation_fee")

                if is_consult and payment.user:
                    from subscriptions.models import UserSubscription
                    sub = UserSubscription.objects.filter(user=payment.user, is_active=True).first()
                    if sub:
                        if consult_type == "expert":
                            sub.remaining_expert += 1
                        else:
                            sub.remaining_inhouse += 1
                        sub.save(update_fields=["remaining_inhouse", "remaining_expert"])
                elif payment.user and payment.plan:
                    from subscriptions.services import activate_plan_for_user
                    activate_plan_for_user(user=payment.user, plan=payment.plan)

                logger.info(f"Successfully auto-reconciled payment {payment.id} (order={payment.razorpay_order_id}) to success")
                return True
        except Exception as e:
            logger.debug(f"Razorpay reconciliation probe error with client: {e}")
            continue

    return False


def reconcile_user_pending_payments(user):
    """
    Checks and auto-reconciles any pending payments for this user created in the last 7 days.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return 0

    from subscriptions.models import Payment
    from django.utils import timezone
    from datetime import timedelta

    since = timezone.now() - timedelta(days=7)
    pending_payments = Payment.objects.filter(
        user=user,
        status="pending",
        created_at__gte=since,
    ).exclude(razorpay_order_id__isnull=True).exclude(razorpay_order_id="")

    reconciled_count = 0
    for p in pending_payments:
        if reconcile_pending_payment(p):
            reconciled_count += 1

    return reconciled_count
