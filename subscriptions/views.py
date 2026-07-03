from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings
import razorpay
from rest_framework import status

from .models import Plan, Payment, UserSubscription
from .serializers import PlanSerializer
import hmac
import hashlib
# ✅ Correct — use Django's built-in get_user_model(), works regardless of app name
from django.contrib.auth import get_user_model
User = get_user_model()

class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = (
            UserSubscription.objects
            .filter(
                user=request.user,
                is_active=True,
                plan__plan_type='patient'
            )
            .select_related("plan")
            .first()
        )

        # If no local active plan or it's a FREE plan, check PathyaTech
        if not subscription or subscription.plan.price == 0:
            from subscriptions.utils import check_pathyatech_subscription
            pt_status = check_pathyatech_subscription(request.user.email)
            if pt_status.get("has_active_plan"):
                pt_plan = pt_status.get("plan", {})
                features = pt_plan.get("features", {}) or {}
                
                # Dynamic mapping of PathyaTech plan ID to local Plan ID based on name comparison
                pt_name_lower = pt_plan.get("name", "").lower()
                ti_mapped_name = pt_plan.get("trackintake_plan_name")
                local_plan_id = pt_plan.get("id")
                from subscriptions.models import Plan
                mapped_plan = None
                
                # 1. Check exact match with trackintake_plan_name from PathyaTech
                if ti_mapped_name:
                    mapped_plan = Plan.objects.filter(name__iexact=ti_mapped_name, plan_type="patient").first()
                
                # 2. Fallback to substring matching if no exact match found
                if not mapped_plan:
                    if "premium" in pt_name_lower:
                        mapped_plan = Plan.objects.filter(name__icontains="premium", plan_type="patient").first()
                    elif "silver" in pt_name_lower:
                        mapped_plan = Plan.objects.filter(name__icontains="silver", plan_type="patient").first()
                    elif "basic" in pt_name_lower:
                        mapped_plan = Plan.objects.filter(name__icontains="basic", plan_type="patient").first()
                
                if mapped_plan:
                    local_plan_id = mapped_plan.id

                plan_data = {
                    "id": local_plan_id,
                    "name": pt_plan.get("name"),
                    "plan_type": "patient",
                    "price": pt_plan.get("price"),
                    # Use duration from PathyaTech (90 days for Premium), default 90
                    "duration_days": pt_plan.get("duration_days", 90),
                    
                    # Feature flags from PathyaTech response
                    "weight_tracker_allowed": features.get("weight_tracker_allowed", False),
                    "custom_reminder_allowed": features.get("custom_reminder_allowed", False),
                    "chat_allowed": features.get("chat_allowed", False),
                    "ai_diet_allowed": features.get("ai_diet_allowed", False),
                    "meal_log_allowed": features.get("meal_log_allowed", False),
                    "water_intake_allowed": features.get("water_intake_allowed", False),
                    
                    # TrackIntake-specific feature flags (Premium bundle)
                    "nutrition_search_allowed": features.get("nutrition_search_allowed", True),
                    "appointment_allowed": features.get("appointment_allowed", True),
                    "BMI_Calculator_allowed": features.get("BMI_Calculator_allowed", True),
                    "Fat_Calculator_allowed": features.get("Fat_Calculator_allowed", True),
                    
                    # Consultation limits
                    "inhouse_consults": features.get("inhouse_consults", 1),
                    "expert_consults": features.get("expert_consults", 0),
                }
                
                return Response({
                    "has_plan": True,
                    "plan": plan_data,
                    "is_active": True,
                    "expires_at": pt_plan.get("expires_at"),
                    "remaining_inhouse": features.get("inhouse_consults", 1),
                    "remaining_expert": features.get("expert_consults", 0),
                })

        if not subscription:
            return Response({
                "has_plan": False,  # ✅ Yeh flag frontend use karega
                "plan": {"name": "No Plan", "price": 0},
                "is_active": False
            })

        return Response({
            "has_plan": True,
            "plan": PlanSerializer(subscription.plan).data,
            "is_active": True,
            "expires_at": subscription.end_date,
            "remaining_inhouse": subscription.remaining_inhouse,
            "remaining_expert": subscription.remaining_expert,
        })



class PlanListView(APIView):
    """
    Public endpoint — used by both logged-in users AND the registration page.
    Pass ?type=nutritionist or ?type=patient to filter by plan type.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        plan_type = request.query_params.get("type", "").strip().lower()
        qs = Plan.objects.filter(is_active=True)
        if plan_type:
            qs = qs.filter(plan_type__iexact=plan_type).order_by("price")
        serializer = PlanSerializer(qs, many=True)
        return Response(serializer.data)


class CreateOrderView(APIView):
    """Authenticated users upgrading/purchasing a plan."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get("plan_id")

        if not plan_id:
            return Response({"error": "plan_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({"error": "Invalid or inactive plan"}, status=status.HTTP_404_NOT_FOUND)

        amount_in_paise = int(plan.price * 100)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1,
        })

        Payment.objects.create(
            user=request.user,
            plan=plan,
            amount=plan.price,
            razorpay_order_id=order["id"],
            status="pending",
        )

        return Response({
            "order_id": order["id"],
            "amount": amount_in_paise,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "plan": {"id": plan.id, "name": plan.name, "price": plan.price}
        }, status=status.HTTP_201_CREATED)


class UserRegistrationOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        email = request.data.get("email", "").strip().lower()

        if not plan_id or not email:
            return Response(
                {"error": "plan_id and email are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Block if user already exists
        if User.objects.filter(email=email, is_active=True).exists():
            return Response(
                {"error": "An account with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True, plan_type="patient")
        except Plan.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive plan"},
                status=status.HTTP_404_NOT_FOUND
            )

        if plan.price == 0:
            return Response(
                {"error": "This is a free plan. No payment required — proceed directly to registration."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Don't create a duplicate if they already have a successful payment
        already_paid = Payment.objects.filter(
            pending_email=email,
            plan=plan,
            status="success",
            user__isnull=True,
        ).exists()
        # AFTER (returns 200 with a flag — frontend can detect and skip plan screen)
        if already_paid:
            return Response(
                {
                    "already_paid": True,
                    "message": "Payment already completed for this email. Proceed to registration.",
                },
                status=status.HTTP_200_OK
            )

        amount_in_paise = int(plan.price * 100)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"email": email, "type": "user_registration"},
        })

        Payment.objects.create(
            user=None,
            plan=plan,
            amount=plan.price,
            razorpay_order_id=order["id"],
            status="pending",
            pending_email=email,
        )

        return Response({
            "order_id": order["id"],
            "amount": amount_in_paise,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "plan": {"id": plan.id, "name": plan.name, "price": plan.price}
        }, status=status.HTTP_201_CREATED)

class NutritionistRegistrationOrderView(APIView):
    """
    Public endpoint — creates a Razorpay order for a nutritionist
    BEFORE they have an account. No auth required.

    Same free plan guard as UserRegistrationOrderView.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        email = request.data.get("email", "").strip().lower()
        full_name = request.data.get("full_name", "")

        if not plan_id or not email:
            return Response(
                {"error": "plan_id and email are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True, plan_type="nutritionist")
        except Plan.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive plan"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Free plan — no payment needed
        if plan.price == 0:
            return Response(
                {"error": "This is a free plan. No payment required — proceed directly to registration."},
                status=status.HTTP_400_BAD_REQUEST
            )

        amount_in_paise = int(plan.price * 100)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "email": email,
                "full_name": full_name,
                "type": "nutritionist_registration",
            },
        })

        Payment.objects.create(
            user=None,
            plan=plan,
            amount=plan.price,
            razorpay_order_id=order["id"],
            status="pending",
            pending_email=email,
        )

        return Response({
            "order_id": order["id"],
            "amount": amount_in_paise,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "plan": {"id": plan.id, "name": plan.name, "price": plan.price}
        }, status=status.HTTP_201_CREATED)

# class VerifyPaymentView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         order_id = request.data.get("razorpay_order_id")
#         payment_id = request.data.get("razorpay_payment_id")
#         signature = request.data.get("razorpay_signature")

#         if not all([order_id, payment_id, signature]):
#             return Response({"error": "Missing payment fields"}, status=400)

#         # Verify signature
#         expected = hmac.new(
#             settings.RAZORPAY_KEY_SECRET.encode(),
#             f"{order_id}|{payment_id}".encode(),
#             hashlib.sha256
#         ).hexdigest()

#         if not hmac.compare_digest(expected, signature):
#             return Response({"error": "Invalid signature"}, status=400)

#         try:
#             payment = Payment.objects.get(
#                 razorpay_order_id=order_id,
#                 status="pending",
#             )
#             payment.razorpay_payment_id = payment_id
#             payment.status = "success"
#             payment.save(update_fields=["razorpay_payment_id", "status"])

#             if payment.user:
#                 from .services import activate_plan_for_user
#                 activate_plan_for_user(user=payment.user, plan=payment.plan)

#         except Payment.DoesNotExist:
#             pass

#         return Response({"status": "ok"})
class VerifyPaymentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        order_id = request.data.get("razorpay_order_id")
        payment_id = request.data.get("razorpay_payment_id")
        signature = request.data.get("razorpay_signature")

        if not all([order_id, payment_id, signature]):
            return Response({"error": "Missing payment fields"}, status=400)

        # Signature verify karo
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return Response({"error": "Invalid signature"}, status=400)

        # ✅ Normal plan payment
        try:
            payment = Payment.objects.get(
                razorpay_order_id=order_id,
                status="pending",
            )
            payment.razorpay_payment_id = payment_id
            payment.status = "success"
            payment.save(update_fields=["razorpay_payment_id", "status"])

            if payment.user:
                from .services import activate_plan_for_user
                activate_plan_for_user(user=payment.user, plan=payment.plan)

        except Payment.DoesNotExist:
            pass

        # ✅ Consultation fee payment — Razorpay se notes fetch karo
        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            rzp_payment = client.payment.fetch(payment_id)
            notes = rzp_payment.get("notes", {})

            if notes.get("type") == "consultation_fee":
                consult_type = notes.get("consult_type")
                user_id = notes.get("user_id")

                subscription = UserSubscription.objects.filter(
                    user_id=user_id,
                    is_active=True
                ).first()

                if subscription:
                    if consult_type == "inhouse":
                        subscription.remaining_inhouse += 1
                    elif consult_type == "expert":
                        subscription.remaining_expert += 1
                    subscription.save(
                        update_fields=["remaining_inhouse", "remaining_expert"]
                    )
                    print(f"✅ Consultation added: {consult_type} for user {user_id}")

        except Exception as e:
            print(f"❌ Consultation fee update error: {e}")

        return Response({"status": "ok"})
class PayConsultationFeeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        consult_type = request.data.get("consult_type")

        if consult_type not in ["inhouse", "expert"]:
            return Response({"error": "Invalid consult_type"}, status=400)

        # ✅ User ki active subscription se plan lo
        from subscriptions.utils import get_active_subscription
        subscription = get_active_subscription(request.user)

        if not subscription:
            return Response({"error": "No active subscription"}, status=400)

        # ✅ Plan se fee lo
        if consult_type == "inhouse":
            amount = subscription.plan.inhouse_consultation_fee
        else:
            amount = subscription.plan.expert_consultation_fee

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        order = client.order.create({
            "amount": amount * 100,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "user_id": request.user.id,
                "consult_type": consult_type,
                "type": "consultation_fee"
            }
        })

        return Response({
            "order_id": order["id"],
            "amount": amount * 100,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "consult_type": consult_type
        })