import hmac
import hashlib
import json
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Payment
from .services import activate_plan_for_user


class RazorpayWebhook(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        received_signature = request.headers.get("X-Razorpay-Signature")

        # ✅ Fixed: hmac.new() → hmac.new() is correct but must be called
        #    without keyword args in some Python versions. Use positional args.
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        if not received_signature:
            return Response({"error": "Missing signature"}, status=400)

        if not hmac.compare_digest(received_signature, expected_signature):
            return Response({"error": "Invalid signature"}, status=400)

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=400)

        event = data.get("event")

        if event == "payment.captured":
            entity = data["payload"]["payment"]["entity"]
            order_id = entity["order_id"]
            payment_id = entity["id"]

            try:
                payment = Payment.objects.get(
                    razorpay_order_id=order_id,
                    status="pending",
                )
                payment.razorpay_payment_id = payment_id
                payment.status = "success"
                payment.save(update_fields=["razorpay_payment_id", "status"])

                if payment.user:
                    activate_plan_for_user(user=payment.user, plan=payment.plan)

            except Payment.DoesNotExist:
                pass  # Idempotent — already processed or unknown order

        return Response({"status": "ok"})