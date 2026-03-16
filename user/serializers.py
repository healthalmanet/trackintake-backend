from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.core.cache import cache

from diet.models import DietFeedback
from .models import User, Feedback


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT login serializer.
    - Adds role, email, full_name to token payload
    - Blocks unverified nutritionists from logging in
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # ── Block unverified nutritionists ────────────────────────────────────
        if user.role == "nutritionist":
            profile = getattr(user, "nutritionist_profile", None)
            if profile is None or not profile.is_verified:
                raise serializers.ValidationError(
                    "Your account is pending admin verification. "
                    "You will be notified once approved."
                )

        # ── Add custom claims to response ─────────────────────────────────────
        data["role"] = user.role
        data["email"] = user.email
        data["full_name"] = user.full_name
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.full_name
        return token


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


class FeedbackSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Feedback
        fields = ['id', 'user_email', 'message', 'rating', 'created_at']


class DietFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietFeedback
        fields = ['id', 'recommendation', 'user', 'day', 'feedback', 'rating', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']


class EmailSerializer(serializers.Serializer):
    """Serializer for the first step: getting the user's email."""
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("A user with this email is already registered.")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for the second step: verifying the OTP."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate_email(self, value):
        return value.lower()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Final registration serializer.

    Payment gate logic:
      - FREE plan exists (price=0, is_active=True) for the role type
        → skip payment entirely, auto-assign the free plan on account creation.
      - Paid plan exists (successful pending Payment for this email)
        → link and activate that plan on account creation.
      - Neither exists
        → block registration with a clear error.

    Admin control:
      - Add a free plan (price=0) in Django admin → payment page is skipped for all new users.
      - Remove/deactivate the free plan → users must purchase before registering.
    """
    full_name = serializers.CharField(required=True)
    verification_token = serializers.CharField(write_only=True)
    role = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ['email', 'full_name', 'password', 'verification_token', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_role(self, value):
        allowed_roles = ['user', 'nutritionist']
        if value not in allowed_roles:
            raise serializers.ValidationError(
                f"Invalid role. Allowed roles for registration are: {', '.join(allowed_roles)}"
            )
        return value

    def validate(self, data):
        data['email'] = data['email'].lower()
        email = data.get('email')
        token = data.get('verification_token')

        # ── Step 1: Validate OTP verification token ───────────────────────────
        cached_token = cache.get(f"verification_token_{email}")
        if not cached_token:
            raise serializers.ValidationError({
                "token": (
                    "Verification token expired. Please re-verify your email. "
                    "Your payment has been saved and will be linked automatically when you complete registration."
                )
            })
        if cached_token != token:
            raise serializers.ValidationError({
                "token": "Invalid verification token."
            })

        # ── Step 2: Check free plan or paid payment ───────────────────────────
        from subscriptions.models import Payment, Plan

        role = data.get('role', 'user')
        plan_type = 'nutritionist' if role == 'nutritionist' else 'patient'

        # Is there a free (price=0) active plan for this role type?
        free_plan_exists = Plan.objects.filter(
            plan_type=plan_type,
            price=0,
            is_active=True,
        ).exists()

        # Is there a successful pre-registration payment for this email?
        has_paid = Payment.objects.filter(
            pending_email=email,
            status="success",
            user__isnull=True,
        ).exists()

        if not free_plan_exists and not has_paid:
            raise serializers.ValidationError({
                "payment": "Please purchase a plan before completing registration."
            })

        return data

    def create(self, validated_data):
        validated_data.pop('verification_token', None)
        email = validated_data['email']  # already lowercased in validate()
        full_name = validated_data['full_name']
        password = validated_data['password']
        role = validated_data.get('role', 'user')

        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            password=password,
            role=role,
        )
        cache.delete(f"verification_token_{email}")

        from subscriptions.models import Payment, Plan
        from subscriptions.services import activate_plan_for_user

        # ── Priority 1: Link a successful paid pending payment ─────────────────
        # Paid plan takes priority over free plan (in case admin forgot to
        # deactivate the free plan after a user already paid).
        pending_payment = (
            Payment.objects
            .filter(
                pending_email=email,
                status="success",
                user__isnull=True,
            )
            .select_related("plan")
            .order_by("-created_at")
            .first()
        )

        if pending_payment:
            pending_payment.user = user
            pending_payment.save(update_fields=["user"])
            activate_plan_for_user(user=user, plan=pending_payment.plan)

        else:
            # ── Priority 2: Auto-assign the free plan ──────────────────────────
            plan_type = 'nutritionist' if role == 'nutritionist' else 'patient'
            free_plan = (
                Plan.objects
                .filter(plan_type=plan_type, price=0, is_active=True)
                .order_by("id")
                .first()
            )
            if free_plan:
                activate_plan_for_user(user=user, plan=free_plan)

        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Controls which user data is sent to the frontend.
    """
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role')