from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings
import razorpay
from rest_framework import status 

from .models import Plan, Payment
from .serializers import PlanSerializer
from .models import UserSubscription


class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = (
            UserSubscription.objects
            .filter(user=request.user, is_active=True)
            .select_related("plan")
            .first()
        )

        if not subscription:
            return Response({
                "plan": {"name": "Free", "price": 0},
                "is_active": True
            })

        return Response({
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
        plan_type = request.query_params.get("type")  # 'nutritionist' | 'patient' | None
        qs = Plan.objects.filter(is_active=True).order_by("price")
        if plan_type:
            qs = qs.filter(plan_type=plan_type)
        serializer = PlanSerializer(qs, many=True)
        return Response(serializer.data)


class CreateOrderView(APIView):
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


class NutritionistRegistrationOrderView(APIView):
    """
    Public endpoint — creates a Razorpay order for a nutritionist
    BEFORE they have an account. No auth required.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        email = request.data.get("email", "").strip().lower()
        full_name = request.data.get("full_name", "")

        if not plan_id or not email:
            return Response({"error": "plan_id and email are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True, plan_type="nutritionist")
        except Plan.DoesNotExist:
            return Response({"error": "Invalid or inactive plan"}, status=status.HTTP_404_NOT_FOUND)

        amount_in_paise = int(plan.price * 100)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"email": email, "full_name": full_name, "type": "nutritionist_registration"},
        })

        Payment.objects.create(
            user=None,               # user doesn't exist yet
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