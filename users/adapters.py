from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.google.provider import GoogleProvider
from .models import User

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    '''
    Custom adapter to handle user population from social accounts.
    This adapter is used to populate the user instance with data from the social account.
    It is particularly useful for Google accounts where we want to extract specific fields.
    '''
    def populate_user(self, request, sociallogin, **kwargs):
        # Call the parent method to get the user instance
        user = super().populate_user(request, sociallogin, **kwargs)

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