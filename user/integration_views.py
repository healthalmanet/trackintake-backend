import copy
import hmac
import hashlib
import razorpay
from datetime import date, datetime
from rest_framework import status, permissions, serializers, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor

from userProfile.models import UserProfile, LabReport
from userProfile.serializers import LabReportSerializer
from subscriptions.models import Plan, Payment, UserSubscription
from subscriptions.services import activate_plan_for_user
from diet.models import DietRecommendation
from diet.serializers import DietRecommendationSerializer
from utils.generative import (
    generate_ai_plan_for_patient,
    _serialize_user_profile,
    _serialize_lab_report,
    _calculate_target_nutrients,
)

User = get_user_model()
executor = ThreadPoolExecutor(max_workers=2)

class IntegrationRegisterView(APIView):
    """
    Public API endpoint to register a patient user directly without OTP verification.
    Optionally accepts profile/health profile fields to pre-create the user profile.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", "").strip().lower()
        full_name = request.data.get("full_name", "").strip()
        password = request.data.get("password")
        role = request.data.get("role", "user").strip().lower()

        if not email or not full_name or not password:
            return Response(
                {"error": "email, full_name, and password are required fields."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce that this endpoint is only for patient users
        if role != "user":
            return Response(
                {"error": "This integration endpoint is exclusively for registering patient users (role='user')."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "A user with this email is already registered."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    email=email,
                    full_name=full_name,
                    password=password,
                    role="user"
                )

                # Create UserProfile
                profile_fields = [
                    'date_of_birth', 'country', 'city', 'mobile_number', 'gender', 
                    'height_cm', 'weight_kg', 'occupation', 'activity_level', 'goal', 
                    'diet_type', 'allergies', 'is_diabetic', 'is_hypertensive', 
                    'has_heart_condition', 'has_thyroid_disorder', 'has_arthritis', 
                    'has_gastric_issues', 'other_chronic_condition', 'family_history',
                    'is_pregnant', 'due_date', 'is_breastfeeding'
                ]
                
                profile_data = {
                    field: request.data.get(field)
                    for field in profile_fields
                    if request.data.get(field) is not None
                }
                
                # Ensure gender is provided since it has choices and is not nullable
                if 'gender' not in profile_data:
                    profile_data['gender'] = 'other'

                UserProfile.objects.create(user=user, **profile_data)

                # Auto-assign the FREE plan if one exists
                free_plan = Plan.objects.filter(plan_type="patient", price=0, is_active=True).first()
                if free_plan:
                    activate_plan_for_user(user=user, plan=free_plan)

            # Generate JWT Tokens
            refresh = RefreshToken.for_user(user)
            tokens = {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }

            return Response({
                "message": "User registered successfully.",
                "tokens": tokens,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Registration failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IntegrationPlanListView(APIView):
    """
    Public endpoint to retrieve the list of active subscription plans for patients.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        # Exclusively return patient plans
        plans = Plan.objects.filter(is_active=True, plan_type="patient").order_by("price")
        
        data = []
        for plan in plans:
            data.append({
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "duration_days": plan.duration_days,
                "plan_type": plan.plan_type,
                "features": {
                    "weight_tracker_allowed": plan.weight_tracker_allowed,
                    "nutrition_search_allowed": plan.nutrition_search_allowed,
                    "custom_reminder_allowed": plan.custom_reminder_allowed,
                    "chat_allowed": plan.chat_allowed,
                    "appointment_allowed": plan.appointment_allowed,
                    "ai_diet_allowed": plan.ai_diet_allowed,
                    "BMI_Calculator_allowed": plan.BMI_Calculator_allowed,
                    "Fat_Calculator_allowed": plan.Fat_Calculator_allowed,
                    "meal_log_allowed": plan.meal_log_allowed,
                    "water_intake_allowed": plan.water_intake_allowed,
                },
                "consultations": {
                    "expert_consults": plan.expert_consults,
                    "inhouse_consults": plan.inhouse_consults,
                    "inhouse_consultation_fee": plan.inhouse_consultation_fee,
                    "expert_consultation_fee": plan.expert_consultation_fee,
                }
            })
        return Response(data, status=status.HTTP_200_OK)


class IntegrationCreateOrderView(APIView):
    """
    Authenticated endpoint to initiate a real Razorpay plan purchase.
    Creates a pending Payment record and returns order info to the third-party app.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users can purchase subscription plans."},
                status=status.HTTP_403_FORBIDDEN
            )

        plan_id = request.data.get("plan_id")
        if not plan_id:
            return Response(
                {"error": "plan_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True, plan_type="patient")
        except Plan.DoesNotExist:
            return Response(
                {"error": "Invalid, inactive, or non-patient plan ID."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Create order in Razorpay
            amount_in_paise = int(plan.price * 100)
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            order = client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1,
            })

            # Save order details in database
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

        except Exception as e:
            return Response(
                {"error": f"Failed to create payment order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IntegrationVerifyPaymentView(APIView):
    """
    Authenticated endpoint to verify the Razorpay payment signature
    and activate the corresponding subscription.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users can perform payment verification."},
                status=status.HTTP_403_FORBIDDEN
            )

        order_id = request.data.get("razorpay_order_id")
        payment_id = request.data.get("razorpay_payment_id")
        signature = request.data.get("razorpay_signature")

        if not all([order_id, payment_id, signature]):
            return Response(
                {"error": "Missing razorpay_order_id, razorpay_payment_id, or razorpay_signature."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify signature
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return Response({"error": "Invalid razorpay payment signature."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                payment = Payment.objects.get(razorpay_order_id=order_id, status="pending")
                payment.razorpay_payment_id = payment_id
                payment.status = "success"
                payment.save(update_fields=["razorpay_payment_id", "status"])

                # Activate subscription
                activate_plan_for_user(user=request.user, plan=payment.plan)

            # Retrieve active subscription details
            subscription = UserSubscription.objects.filter(user=request.user, is_active=True).first()
            return Response({
                "message": "Payment verified and plan activated successfully.",
                "subscription": {
                    "id": subscription.id,
                    "plan_name": payment.plan.name,
                    "plan_type": payment.plan.plan_type,
                    "start_date": subscription.start_date,
                    "end_date": subscription.end_date,
                    "is_active": subscription.is_active
                }
            }, status=status.HTTP_200_OK)

        except Payment.DoesNotExist:
            return Response(
                {"error": "Pending payment record for this order_id not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Verification failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IntegrationCheckSubscriptionView(APIView):
    """
    Authenticated endpoint to check if the user has an active subscription.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users can query subscription status."},
                status=status.HTTP_403_FORBIDDEN
            )

        subscription = UserSubscription.objects.filter(
            user=request.user,
            is_active=True,
            plan__plan_type="patient"
        ).select_related("plan").first()

        if not subscription:
            return Response({
                "has_active_plan": False,
                "plan": None
            }, status=status.HTTP_200_OK)

        return Response({
            "has_active_plan": True,
            "plan": {
                "id": subscription.plan.id,
                "name": subscription.plan.name,
                "price": subscription.plan.price,
                "expires_at": subscription.end_date
            }
        }, status=status.HTTP_200_OK)


class IntegrationLabReportViewSet(viewsets.ModelViewSet):
    """
    Authenticated ViewSet for managing lab reports (health profile history) for patient users.
    Allows listing, creating, retrieving, updating, and deleting lab records.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LabReportSerializer

    def get_queryset(self):
        if self.request.user.role != "user":
            return LabReport.objects.none()
        return LabReport.objects.filter(user=self.request.user).order_by("-report_date")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users (role='user') can create lab reports."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users (role='user') can update lab reports."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users (role='user') can delete lab reports."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


class IntegrationUserProfileSerializer(serializers.ModelSerializer):
    bmi = serializers.FloatField(read_only=True)
    current_trimester = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserProfile
        exclude = ('user',)


class IntegrationUserProfileView(APIView):
    """
    Authenticated endpoint to view or update the user's profile and health profile.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = IntegrationUserProfileSerializer

    def get(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users (role='user') have profiles accessible through this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        # For patients, fetch UserProfile
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={"gender": "other"}
        )
        serializer = self.serializer_class(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Profile updates through this endpoint are exclusively supported for patient users."},
                status=status.HTTP_403_FORBIDDEN
            )

        profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={"gender": "other"}
        )
        serializer = self.serializer_class(profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Profile updates through this endpoint are exclusively supported for patient users."},
                status=status.HTTP_403_FORBIDDEN
            )

        profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={"gender": "other"}
        )
        serializer = self.serializer_class(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IntegrationDietPlanView(APIView):
    """
    Authenticated endpoint to view diet recommendations.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.role != "user":
            return Response(
                {"error": "Only patient users (role='user') can view diet recommendations via this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if there is an active subscription
        subscription = UserSubscription.objects.filter(user=request.user, is_active=True).first()
        if not subscription:
            return Response(
                {"error": "No active subscription plan found. Please subscribe to a plan first."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Fetch the latest recommendation
        plan = DietRecommendation.objects.filter(user=request.user).order_by("-created_at").first()
        if not plan:
            return Response({
                "status_code": "NO_PLAN_FOUND",
                "message": "No diet plan has been generated for your profile yet. Please contact your nutritionist to generate one."
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = DietRecommendationSerializer(plan)
        return Response({
            "status_code": plan.status.upper(),
            "message": f"Diet plan status: {plan.get_status_display()}.",
            "plan_data": serializer.data
        }, status=status.HTTP_200_OK)
