from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model 

from users.models import User, Profile 
from leave_mgt.models import LeaveCredits 

class Command(BaseCommand):
    help = "Creates LeaveCredits for users who don't have them yet."

    def handle(self, *args, **options):
        User = get_user_model()  # Get your User model dynamically
        for user in User.objects.all():
            if hasattr(user, 'profile'):  # Check if the user has a Profile
                LeaveCredits.objects.get_or_create(employee=user.profile)

        self.stdout.write(self.style.SUCCESS(
            'Successfully created missing LeaveCredits!'
        ))