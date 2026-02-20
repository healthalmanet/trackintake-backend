import hmac
import hashlib
import json

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Payment, UserSubscription
from .services import activate_plan_for_user


class RazorpayWebhook(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        received_signature = request.headers.get("X-Razorpay-Signature")

        expected_signature = hmac.new(
            key=settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        # ❌ Invalid signature → reject
        if not hmac.compare_digest(received_signature, expected_signature):
            return Response({"error": "Invalid signature"}, status=400)

        data = json.loads(payload)
        event = data.get("event")

        if event == "payment.captured":
            entity = data["payload"]["payment"]["entity"]

            order_id = entity["order_id"]
            payment_id = entity["id"]

            try:
                payment = Payment.objects.get(
                    razorpay_order_id=order_id,
                    status="pending"
                )

                payment.razorpay_payment_id = payment_id
                payment.status = "success"
                payment.save()

                # ✅ THIS IS THE FIX
                activate_plan_for_user(
                    user=payment.user,
                    plan=payment.plan
                )

            except Payment.DoesNotExist:
                pass


        return Response({"status": "ok"})
