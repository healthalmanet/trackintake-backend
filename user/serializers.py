from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.core.cache import cache  # <-- THIS IS THE FIX

from diet.models import DietFeedback
from .models import User, Feedback


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        token['full_name'] = user.full_name  # ✅ Add full_name to the token payload
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['email'] = self.user.email
        data['full_name'] = self.user.full_name  # ✅ Add full_name to response body
        return data



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
        # Check if a user with this email is already registered and active
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("A user with this email is already registered.")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for the second step: verifying the OTP."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


# class RegisterSerializer(serializers.ModelSerializer):
#     """
#     Final registration serializer.
#     Requires a verification token to ensure the email was proven to be owned by the user.
#     """
#     full_name = serializers.CharField(required=True)
#     # The verification_token is sent by the client but not saved to the model.
#     verification_token = serializers.CharField(write_only=True)

#     class Meta:
#         model = User
#         fields = ['email', 'full_name', 'password', 'verification_token']
#         extra_kwargs = {'password': {'write_only': True}}

#     def validate(self, data):
#         """
#         Validate the verification token.
#         """
#         email = data.get('email')
#         token = data.get('verification_token')

#         cached_token = cache.get(f"verification_token_{email}")

#         if not cached_token:
#             raise serializers.ValidationError({"token": "Verification token has expired or is invalid. Please start over."})
        
#         if cached_token != token:
#             raise serializers.ValidationError({"token": "Invalid verification token."})
        
#         return data

#     def create(self, validated_data):
#         """
#         Create the user now that the token has been validated.
#         """
#         # Remove the token as it's not a field on the User model
#         validated_data.pop('verification_token')
        
#         email = validated_data.get('email')
        
#         # We can now safely create an active user
#         user = User.objects.create_user(**validated_data)
        
#         # Clean up the cache by deleting the used token
#         cache.delete(f"verification_token_{email}")
        
#         return user
   
   
   
class RegisterSerializer(serializers.ModelSerializer):
    """
    Final registration serializer.
    Requires a verification token to ensure the email was proven to be owned by the user.
    """
    full_name = serializers.CharField(required=True)
    # The verification_token is sent by the client but not saved to the model.
    verification_token = serializers.CharField(write_only=True)
    
    # Make role optional on input. If not provided, the model's default ('user') will be used.
    role = serializers.CharField(required=False)

    class Meta:
        model = User
        # Add 'role' to the list of fields
        fields = ['email', 'full_name', 'password', 'verification_token', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_role(self, value):
        """
        Ensures users can only register with allowed roles.
        Prevents anyone from registering as an 'admin' or 'owner'.
        """
        # Define which roles are allowed for self-registration
        allowed_roles = ['user', 'nutritionist']
        
        if value not in allowed_roles:
            raise serializers.ValidationError(
                f"Invalid role. Allowed roles for registration are: {', '.join(allowed_roles)}"
            )
        return value

    def validate(self, data):
        """
        Validate the verification token.
        """
        email = data.get('email')
        token = data.get('verification_token')

        cached_token = cache.get(f"verification_token_{email}")

        if not cached_token:
            raise serializers.ValidationError({"token": "Verification token has expired or is invalid. Please start over."})
        
        if cached_token != token:
            raise serializers.ValidationError({"token": "Invalid verification token."})
        
        return data

    def create(self, validated_data):
        """
        Create the user now that the token has been validated.
        """
        validated_data.pop('verification_token')
        email = validated_data.get('email')
        
        # This will now work perfectly because `create_user` accepts the 'role' key.
        # If 'role' is not in validated_data, our UserManager's default 'user' will be used.
        user = User.objects.create_user(**validated_data)
        
        cache.delete(f"verification_token_{email}")
        
        return user 
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
    
class UserDetailSerializer(serializers.ModelSerializer):
    """
    This serializer is used to control which user data is sent to the frontend.
    """
    class Meta:
        model = User
        # List all the fields you want in the response!
        fields = ('id', 'email', 'full_name', 'role')



