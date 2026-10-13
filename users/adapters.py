from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    def new_user(self, request):
        user = super().new_user(request)
        user._public_signup = True
        return user

    @transaction.atomic
    def save_user(self, request, user, form, commit=True):
        user._public_signup = True
        user.is_staff = False
        user.is_superuser = False
        return super().save_user(request, user, form, commit=commit)

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def new_user(self, request, sociallogin):
        user = super().new_user(request, sociallogin)
        user._social_signup = True
        return user

    def populate_user(self, request, sociallogin, data=None):
        user = super().populate_user(request, sociallogin, data)
        
        if sociallogin.account.provider == GoogleProvider.id:
            extra_data = sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            
            # Use email from extra_data or common_fields
            user.email = extra_data.get('email', '') or (data or {}).get('email', '')
        
        return user


    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        try:
            sociallogin.user._public_signup = True
            sociallogin.user._social_signup = True
            logger.info("Attempting to save user from social login...")
            user = super().save_user(request, sociallogin, form)

            user.is_staff = False
            user.save()

            return user

        except Exception as e:
            logger.exception("Error in save_user during Google login")
            raise  # re-raise so Django still returns 500, but now you get a clear traceback in logs
