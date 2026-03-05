# nutritionist/permissions.py

from rest_framework.permissions import BasePermission

class IsVerifiedNutritionist(BasePermission):
    """
    Allows access only to VERIFIED nutritionists.
    """

    message = "Please wait till you are verified by admin."

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.role != 'nutritionist':
            return False

        # Check profile + verification
        profile = getattr(user, 'nutritionist_profile', None)
        if not profile:
            return False

        return profile.is_verified
