from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
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

        # 🟢 Default = Free
        if not subscription:
            return Response({
                "plan": {
                    "name": "Free",
                    "price": 0
                },
                "is_active": True
            })

        return Response({
            "plan": PlanSerializer(subscription.plan).data,
            "is_active": True,
            "expires_at": subscription.end_date,
            "remaining_inhouse": subscription.remaining_inhouse,
            "remaining_expert": subscription.remaining_expert,
        })



# 🔹 List all active plans
class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True).order_by("price")
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)


# 🔹 Create Razorpay order
class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]
    print("RAZORPAY_KEY_ID:", settings.RAZORPAY_KEY_ID)
    print("RAZORPAY_KEY_SECRET exists:", bool(settings.RAZORPAY_KEY_SECRET))

    def post(self, request):
        plan_id = request.data.get("plan_id")

        if not plan_id:
            return Response(
                {"error": "plan_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive plan"},
                status=status.HTTP_404_NOT_FOUND
            )

        # ✅ Amount is fetched ONLY from DB (Plan model)
        plan_price_rupees = plan.price
        amount_in_paise = int(plan_price_rupees * 100)

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1,
        })

        Payment.objects.create(
            user=request.user,
            plan=plan,
            amount=plan_price_rupees,   # store rupees in DB
            razorpay_order_id=order["id"],
            status="pending",
        )

        return Response({
            "order_id": order["id"],
            "amount": amount_in_paise,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "price": plan_price_rupees,
            }
        }, status=status.HTTP_201_CREATED)
