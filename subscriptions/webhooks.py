import hmac
import hashlib
import json
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Payment
from .services import activate_plan_for_user
from subscriptions.models import UserSubscription

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
            notes = entity.get("notes", {})

            # ✅ Consultation fee payment handle karo
            if notes.get("type") == "consultation_fee":
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=notes["user_id"])
                consult_type = notes["consult_type"]
                
                subscription = UserSubscription.objects.filter(
                    user=user, is_active=True
                ).first()
                
                if subscription:
                    if consult_type == "inhouse":
                        subscription.remaining_inhouse += 1
                    elif consult_type == "expert":
                        subscription.remaining_expert += 1
                    subscription.save(update_fields=["remaining_inhouse", "remaining_expert"])
                return Response({"status": "ok"})