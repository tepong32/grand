from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.google.provider import GoogleProvider
from profiles.models import CitizenProfile
from django.utils.text import slugify
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def new_user(self, request, sociallogin):
        # Fix: must accept 'sociallogin' param
        user = super().new_user(request, sociallogin)

        # Basic prefilling handled here if needed (also safe in populate_user)
        return user

    def populate_user(self, request, sociallogin, data=None):
        # Prefill user fields before saving
        user = super().populate_user(request, sociallogin, data)
        if sociallogin.account.provider == GoogleProvider.id:
            extra_data = sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            user.email = sociallogin.account.email or ''
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        # Safety check: ensure user is not accidentally given staff access
        user.is_staff = False
        user.save()

        # Create linked CitizenProfile if it doesn't exist
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
