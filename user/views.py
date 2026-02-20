import random
from django.core.cache import cache  # <-- THIS IS THE FIX
from django.shortcuts import render
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, DjangoUnicodeDecodeError, smart_str # <-- Add smart_str
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import generics, permissions, status, views
import secrets
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter as GoogleOAuth2AdapterV2
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from .models import User # Make sure to import your User model
from rest_framework.permissions import IsAuthenticated
from diet.models import DietRecommendation,DietFeedback
from user.models import User
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from rest_framework import serializers
from user.serializers import DietFeedbackSerializer, FeedbackSerializer, ForgotPasswordSerializer, MyTokenObtainPairSerializer, RegisterSerializer, ResetPasswordSerializer, UserDetailSerializer,EmailSerializer,VerifyOTPSerializer
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
# Create your views here.


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer



class SendOTPView(views.APIView):
    """
    Step 1: Client sends an email. An OTP is generated and sent to that email.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        # If an inactive user exists, we can reuse it, otherwise we don't care.
        # The serializer already prevents active users from getting a new OTP.
        
        otp = f"{random.randint(100000, 999999)}"
        # Cache the OTP for 5 minutes
        cache.set(f"otp_{email}", otp, timeout=300)

        send_mail(
            subject="Your OTP Code",
            message=f"Hi,\n\nYour OTP Code is {otp}. It is valid for 5 minutes.",
            from_email="your-email@example.com",  # CHANGE THIS
            recipient_list=[email],
            fail_silently=False
        )

        return Response({"message": "OTP sent to your email."}, status=status.HTTP_200_OK)


class VerifyOTPView(views.APIView):
    """
    Step 2: Client sends the email and OTP. If valid, issue a verification token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        cached_otp = cache.get(f"otp_{email}")

        if not cached_otp or cached_otp != otp:
            return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        # OTP is correct, delete it
        cache.delete(f"otp_{email}")
        
        # Issue a secure, short-lived verification token
        verification_token = secrets.token_urlsafe(32)
        # Cache the verification token for 10 minutes
        cache.set(f"verification_token_{email}", verification_token, timeout=600)

        return Response(
            {"message": "Email verified successfully.", "verification_token": verification_token},
            status=status.HTTP_200_OK
        )


class RegisterView(generics.CreateAPIView):
    """
    Step 3: Client sends all user details along with the verification token
    to create the final user account.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]









class CustomSocialLoginView(SocialLoginView):
    """
    This is the custom base class that now generates the exact "flat"
    JSON response you want for both Google and Facebook logins.
    """
    client_class = OAuth2Client
    callback_url = 'https://track-eats.onrender.com/dashboard'

    def get_response(self):
        """
        This method is overridden to create a custom response format.
        It's called after the user is successfully logged in.
        """
        # self.user will contain the authenticated user instance.
        
        # 1. Generate the JWT tokens for the user.
        refresh = RefreshToken.for_user(self.user)

        # 2. Manually construct the response dictionary with the desired flat structure.
        response_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': self.user.role,
            'email': self.user.email,
            'full_name': self.user.full_name
        }
        
        # 3. Return the response with a 200 OK status.
        return Response(response_data, status=status.HTTP_200_OK)


# ✅ FIX: Inherit from CustomSocialLoginView
class GoogleLogin(CustomSocialLoginView):
    """
    This view now correctly uses your custom logic to return JWTs.
    """
    adapter_class = GoogleOAuth2AdapterV2
    # The callback_url and client_class are inherited from the parent


# ✅ FIX: Inherit from CustomSocialLoginView
class FacebookLogin(CustomSocialLoginView):
    """
    This view now also uses the same custom logic.
    """
    adapter_class = FacebookOAuth2Adapter
    # The callback_url and client_class are inherited from the parent



    
    
    
    
#Forgot Password
class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = PasswordResetTokenGenerator().make_token(user)
            frontend_url = "https://track-eats.onrender.com/reset-password"
            reset_url = f"{frontend_url}/{uid}/{token}/"

            send_mail(
                subject="Password Reset Request",
                message=f"Hi {user.full_name or user.email},\n\nClick the link to reset your password:\n{reset_url}\n\nIf you didn’t request this, please ignore it.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False
            )
            return Response({'message': 'Password reset link has been sent.'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            # Return 200 to avoid user enumeration
            return Response({'message': 'If this email exists, a password reset link will be sent.'}, status=status.HTTP_200_OK)

class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uidb64 = serializer.validated_data['uidb64']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            uid = smart_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if not PasswordResetTokenGenerator().check_token(user, token):
                return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()
            return Response({'message': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)
        except (DjangoUnicodeDecodeError, User.DoesNotExist):
            return Response({'error': 'Invalid or expired link.'}, status=status.HTTP_400_BAD_REQUEST)
        

class FeedbackCreateView(generics.CreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_diet_feedback(request):
    serializer = DietFeedbackSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response({"message": "Feedback submitted successfully."}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_feedback_for_recommendation(request, recommendation_id):

    feedbacks = DietFeedback.objects.filter(recommendation_id=recommendation_id, user=request.user)
    serializer = DietFeedbackSerializer(feedbacks, many=True)
    return Response(serializer.data)
