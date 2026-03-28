# subscriptions/webhooks.py

import hmac
import hashlib
import json
import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Payment
from .services import activate_plan_for_user
from subscriptions.models import UserSubscription

logger = logging.getLogger(__name__)


class RazorpayWebhook(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        received_signature = request.headers.get("X-Razorpay-Signature")

        if not received_signature:
            return Response({"error": "Missing signature"}, status=400)

        # ── Verify webhook signature ─────────────────────────────
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(received_signature, expected_signature):
            return Response({"error": "Invalid signature"}, status=400)

        # ── Parse payload ────────────────────────────────────────
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=400)

        event = data.get("event")
        logger.info(f"Razorpay webhook received: {event}")

        # ── Only handle payment.captured ─────────────────────────
        if event != "payment.captured":
            return Response({"status": "ignored"}, status=200)

        try:
            entity   = data["payload"]["payment"]["entity"]
            order_id = entity.get("order_id")
            notes    = entity.get("notes", {})
        except (KeyError, TypeError) as e:
            logger.error(f"Webhook payload parsing error: {e}")
            return Response({"error": "Malformed payload"}, status=400)

        # ── Case 1: Consultation fee payment ─────────────────────
        if notes.get("type") == "consultation_fee":
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()

                user         = User.objects.get(id=notes["user_id"])
                consult_type = notes.get("consult_type")

                subscription = UserSubscription.objects.filter(
                    user=user, is_active=True
                ).first()

                if subscription:
                    if consult_type == "inhouse":
                        subscription.remaining_inhouse += 1
                    elif consult_type == "expert":
                        subscription.remaining_expert += 1
                    subscription.save(
                        update_fields=["remaining_inhouse", "remaining_expert"]
                    )
                    logger.info(f"✅ Consultation added: {consult_type} for user {user.id}")
                else:
                    logger.warning(f"No active subscription found for user {notes['user_id']}")

            except Exception as e:
                logger.error(f"Consultation fee webhook error: {e}")
                # Return 200 so Razorpay doesn't retry — log and move on
            return Response({"status": "ok"}, status=200)

        # ── Case 2: Plan purchase (registration or upgrade) ──────
        try:
            payment = Payment.objects.filter(
                razorpay_order_id=order_id,
            ).first()

            if not payment:
                logger.warning(f"Webhook: No Payment record found for order_id={order_id}")
                return Response({"status": "ok"}, status=200)

            # Idempotency — skip if already processed
            if payment.status == "success":
                logger.info(f"Webhook: Payment {order_id} already marked success, skipping.")
                return Response({"status": "ok"}, status=200)

            # Mark payment as successful
            payment.razorpay_payment_id = entity.get("id", "")
            payment.status = "success"
            payment.save(update_fields=["razorpay_payment_id", "status"])
            logger.info(f"✅ Payment marked success: order_id={order_id}")

            # Activate plan for logged-in users who upgraded
            if payment.user:
                activate_plan_for_user(user=payment.user, plan=payment.plan)
                logger.info(f"✅ Plan activated for user {payment.user.id}")

            # For registration payments (pending_email set, no user yet)
            # Account creation happens via registerUser on frontend after payment.
            # Webhook just confirms the payment is captured.

        except Exception as e:
            logger.error(f"Plan payment webhook error: {e}")
            # Return 200 to stop Razorpay retrying — error is logged
            return Response({"status": "error_logged"}, status=200)

        return Response({"status": "ok"}, status=200)