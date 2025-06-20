from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.google.provider import GoogleProvider
from profiles.models import CitizenProfile
from django.utils.text import slugify
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    # Optional: you can customize normal email-based signup behavior here
    pass

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def new_user(self, request, sociallogin):
        return super().new_user(request, sociallogin)

    def populate_user(self, request, sociallogin, data=None):
        user = super().populate_user(request, sociallogin, data)
        
        if sociallogin.account.provider == GoogleProvider.id:
            extra_data = sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            
            # Use email from extra_data or common_fields
            user.email = extra_data.get('email', '') or data.get('email', '') if data else ''
        
        return user


    def save_user(self, request, sociallogin, form=None):
        try:
            logger.info("Attempting to save user from social login...")
            user = super().save_user(request, sociallogin, form)
            logger.info(f"User saved: {user.username} | Email: {user.email}")

            user.is_staff = False
            user.save()

            if not hasattr(user, 'citizenprofile'):
                base_slug = slugify(user.username)
                slug = base_slug
                counter = 1
                while CitizenProfile.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                CitizenProfile.objects.create(
                    user=user,
                    slug=slug,
                    social_auth=True
                )
                logger.info(f"CitizenProfile auto-created for user: {user.username}")
            return user

        except Exception as e:
            logger.exception("Error in save_user during Google login")
            raise  # re-raise so Django still returns 500, but now you get a clear traceback in logs
