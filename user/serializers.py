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
        email = attrs.get("email") or attrs.get("username")
        password = attrs.get("password")
        try:
            data = super().validate(attrs)
        except Exception as e:
            import requests
            from django.conf import settings
            pt_url = f"{getattr(settings, 'PATHYATECH_BACKEND_URL', 'http://localhost:9000').rstrip('/')}/api/auth/login/"
            try:
                pt_response = requests.post(pt_url, json={
                    "email": email,
                    "password": password,
                    "role": "PATIENT"
                }, timeout=5)
                if pt_response.status_code == 200:
                    pt_data = pt_response.json()
                    pt_name = pt_data.get("name") or pt_data.get("full_name") or "Patient"
                    
                    user, created = User.objects.get_or_create(
                        email=email.lower().strip(),
                        defaults={
                            "full_name": pt_name,
                            "role": "user"
                        }
                    )
                    user.set_password(password)
                    user.save()
                    
                    from userProfile.models import UserProfile
                    UserProfile.objects.get_or_create(user=user, defaults={"gender": "other"})
                    
                    from subscriptions.models import Plan
                    from subscriptions.services import activate_plan_for_user
                    free_plan = Plan.objects.filter(plan_type="patient", price=0, is_active=True).first()
                    if free_plan:
                        activate_plan_for_user(user=user, plan=free_plan)
                        
                    data = super().validate(attrs)
                else:
                    raise e
            except Exception:
                raise e

        user = self.user

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
        value = value.lower().strip()
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("A user with this email is already registered.")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for the second step: verifying the OTP."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        return str(value).strip()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Final registration serializer.
    """
    full_name = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    verification_token = serializers.CharField(write_only=True)
    role = serializers.CharField(required=False)

    # Optional Nutritionist Professional & Document Fields
    is_online_available = serializers.BooleanField(required=False, default=True)
    is_offline_available = serializers.BooleanField(required=False, default=False)
    offline_location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    online_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0.00)
    offline_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0.00)
    offline_payment_required = serializers.BooleanField(required=False, default=True)

    gender = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    professional_title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    qualification = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    registration_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issuing_authority = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    years_of_experience = serializers.IntegerField(required=False, default=0)
    current_organization = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    professional_bio = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    languages_spoken = serializers.JSONField(required=False, default=list)
    specializations = serializers.JSONField(required=False, default=list)

    qualification_certificate = serializers.FileField(required=False, allow_null=True)
    registration_certificate = serializers.FileField(required=False, allow_null=True)
    government_id = serializers.FileField(required=False, allow_null=True)
    experience_certificate = serializers.FileField(required=False, allow_null=True)
    additional_certifications = serializers.FileField(required=False, allow_null=True)
    profile_photo = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'email', 'full_name', 'phone_number', 'password', 'verification_token', 'role',
            'is_online_available', 'is_offline_available', 'offline_location',
            'online_price', 'offline_price', 'offline_payment_required',
            'gender', 'date_of_birth', 'professional_title', 'qualification',
            'registration_number', 'issuing_authority', 'years_of_experience',
            'current_organization', 'professional_bio', 'languages_spoken', 'specializations',
            'qualification_certificate', 'registration_certificate', 'government_id',
            'experience_certificate', 'additional_certifications', 'profile_photo'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def to_internal_value(self, data):
        # Create a mutable copy of data while preserving UploadedFile objects
        if hasattr(data, 'copy'):
            mutable_data = data.copy()
        elif hasattr(data, 'dict'):
            mutable_data = data.dict()
        else:
            mutable_data = dict(data)

        # Sanitize empty strings for optional numeric, date, and json fields
        if mutable_data.get('date_of_birth') == '':
            mutable_data['date_of_birth'] = None
        if mutable_data.get('years_of_experience') in ['', None]:
            mutable_data['years_of_experience'] = 0
        if mutable_data.get('online_price') in ['', None]:
            mutable_data['online_price'] = 0.00
        if mutable_data.get('offline_price') in ['', None]:
            mutable_data['offline_price'] = 0.00

        # Sanitize string booleans from FormData
        for b_field in ['is_online_available', 'is_offline_available', 'offline_payment_required']:
            if b_field in mutable_data:
                val = mutable_data[b_field]
                if isinstance(val, str):
                    mutable_data[b_field] = val.lower() == 'true'

        # Parse JSON fields if passed as strings from FormData
        for j_field in ['languages_spoken', 'specializations']:
            if j_field in mutable_data:
                val = mutable_data[j_field]
                if isinstance(val, str):
                    try:
                        import json
                        mutable_data[j_field] = json.loads(val)
                    except Exception:
                        mutable_data[j_field] = []

        return super().to_internal_value(mutable_data)

    def validate_role(self, value):
        allowed_roles = ['user', 'nutritionist']
        if value not in allowed_roles:
            raise serializers.ValidationError(
                f"Invalid role. Allowed roles for registration are: {', '.join(allowed_roles)}"
            )
        return value

    def validate(self, data):
        data['email'] = data['email'].lower().strip()
        email = data.get('email')
        token = data.get('verification_token')

        # Check if user with email already exists
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({
                "email": "An account with this email address already exists. Please log in."
            })

        # ── Step 1: Validate OTP verification token ───────────────────────────
        cached_token = cache.get(f"verification_token_{email}")
        if not cached_token:
            raise serializers.ValidationError({
                "token": "Verification token expired or missing. Please request a new OTP code."
            })
        if str(cached_token).strip() != str(token).strip():
            raise serializers.ValidationError({
                "token": "Invalid OTP verification code."
            })

        return data

    def create(self, validated_data):
        # Extract nutritionist extra fields if present
        is_online_available = validated_data.pop('is_online_available', True)
        is_offline_available = validated_data.pop('is_offline_available', False)
        offline_location = validated_data.pop('offline_location', '')
        online_price = validated_data.pop('online_price', 0.00)
        offline_price = validated_data.pop('offline_price', 0.00)
        offline_payment_required = validated_data.pop('offline_payment_required', True)

        gender = validated_data.pop('gender', '')
        date_of_birth = validated_data.pop('date_of_birth', None)
        professional_title = validated_data.pop('professional_title', '')
        qualification = validated_data.pop('qualification', '')
        registration_number = validated_data.pop('registration_number', '')
        issuing_authority = validated_data.pop('issuing_authority', '')
        years_of_experience = validated_data.pop('years_of_experience', 0)
        current_organization = validated_data.pop('current_organization', '')
        professional_bio = validated_data.pop('professional_bio', '')
        languages_spoken = validated_data.pop('languages_spoken', [])
        specializations = validated_data.pop('specializations', [])

        qualification_certificate = validated_data.pop('qualification_certificate', None)
        registration_certificate = validated_data.pop('registration_certificate', None)
        government_id = validated_data.pop('government_id', None)
        experience_certificate = validated_data.pop('experience_certificate', None)
        additional_certifications = validated_data.pop('additional_certifications', None)
        profile_photo = validated_data.pop('profile_photo', None)

        validated_data.pop('verification_token', None)
        email = validated_data['email']  # already lowercased in validate()
        full_name = validated_data['full_name']
        phone_number = validated_data.get('phone_number', '')
        password = validated_data['password']
        role = validated_data.get('role', 'user')

        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            password=password,
            role=role,
        )
        cache.delete(f"verification_token_{email}")

        # Pre-fill UserProfile
        from userProfile.models import UserProfile
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        if phone_number:
            user_profile.mobile_number = phone_number
        if gender:
            user_profile.gender = gender
        if date_of_birth:
            user_profile.date_of_birth = date_of_birth
        user_profile.save()

        # Pre-fill NutritionistProfile if nutritionist role
        if role == "nutritionist":
            from nutritionist.models import NutritionistProfile
            nutri_profile, _ = NutritionistProfile.objects.get_or_create(user=user)
            nutri_profile.is_online_available = is_online_available
            nutri_profile.is_offline_available = is_offline_available
            nutri_profile.offline_location = offline_location or ""

            nutri_profile.professional_title = professional_title or ""
            nutri_profile.qualification = qualification or ""
            nutri_profile.registration_number = registration_number or ""
            nutri_profile.issuing_authority = issuing_authority or ""
            nutri_profile.years_of_experience = years_of_experience or 0
            nutri_profile.current_organization = current_organization or ""
            nutri_profile.professional_bio = professional_bio or ""
            nutri_profile.languages_spoken = languages_spoken or []
            nutri_profile.specializations = specializations or []

            if qualification_certificate:
                nutri_profile.qualification_certificate = qualification_certificate
            if registration_certificate:
                nutri_profile.registration_certificate = registration_certificate
            if government_id:
                nutri_profile.government_id = government_id
            if experience_certificate:
                nutri_profile.experience_certificate = experience_certificate
            if additional_certifications:
                nutri_profile.additional_certifications = additional_certifications
            if profile_photo:
                nutri_profile.profile_photo = profile_photo

            # Pricing requires admin approval upon registration
            has_price_request = (online_price and float(online_price) > 0) or (offline_price and float(offline_price) > 0)
            if has_price_request:
                nutri_profile.pending_online_price = online_price
                nutri_profile.pending_offline_price = offline_price
                nutri_profile.pending_offline_payment_required = offline_payment_required
                nutri_profile.price_approval_status = "pending"
            else:
                nutri_profile.online_price = online_price
                nutri_profile.offline_price = offline_price
                nutri_profile.offline_payment_required = offline_payment_required
                nutri_profile.price_approval_status = "approved"

            nutri_profile.save()

        from subscriptions.models import Payment, Plan
        from subscriptions.services import activate_plan_for_user

        # ── Priority 1: Link a successful paid pending payment ─────────────────
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
        fields = ('id', 'email', 'full_name', 'phone_number', 'role')