from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        """
        This method is called after a user has been successfully authenticated
        via a social provider, but before the login is finalized. It is the
        perfect place to populate our custom User model with data from the
        social provider.
        """
        # Let the default adapter populate the user with basic data
        # (like email, and if you had them, first_name and last_name)
        user = super().populate_user(request, sociallogin, data)

        # Get the provider-specific data from the sociallogin object
        provider_data = sociallogin.account.extra_data

        # --- This is where we map the data to your custom model ---

        # 1. Populate the 'full_name' field
        # The key for the full name is often 'name' for both Google and Facebook.
        full_name = provider_data.get('name')
        if full_name:
            # Only update the full_name if it's currently empty.
            # You can change this logic if you want the name to always sync.
            if not user.full_name:
                user.full_name = full_name

        # 2. Example for other fields (if you add them later)
        # If your User model had a field like 'profile_picture_url', you could do this:
        #
        # picture_url = provider_data.get('picture') # For Google
        # if picture_url and not hasattr(user, 'profile_picture_url'):
        #     user.profile_picture_url = picture_url

        # Save the user to commit the changes
        
        # Return the populated user object
        return user