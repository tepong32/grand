from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.google.provider import GoogleProvider
from .models import User

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def new_user(self, request, sociallogin):
        # Create a new user instance
        user = super().new_user(request, sociallogin)

        # Populate user fields with data from Google
        if sociallogin.account.provider == GoogleProvider.id:
            extra_data = sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            user.email = sociallogin.account.email  # Ensure the email is set

            # Optionally, you can set middle_name and ext_name if available
            # user.middle_name = extra_data.get('middle_name', '')
            # user.ext_name = extra_data.get('ext_name', '')

        return user

    def populate_user(self, request, sociallogin, data=None):
        # Call the parent method to get the user instance
        user = super().populate_user(request, sociallogin, data)

        # Get the data from the social account
        if sociallogin.account.provider == GoogleProvider.id:
            # Extract the user's information from the social account
            extra_data = sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            user.email = sociallogin.account.email  # Ensure the email is set

            # Optionally, you can set middle_name and ext_name if available
            # user.middle_name = extra_data.get('middle_name', '')
            # user.ext_name = extra_data.get('ext_name', '')

        return user