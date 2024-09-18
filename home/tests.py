from django.test import TestCase
from django.db.models.signals import post_save
from unittest.mock import patch
from django.utils import timezone
from .models import LeaveCounter
from users.models import User
from users.signals import create_profile


class LeaveCounterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Disconnect the signal
        post_save.disconnect(create_profile, sender=User)

        # Create a User and a LeaveCounter for testing
        cls.user = User.objects.create(staff_id='105105745')

        # Manually create a Profile instance for the user
        cls.profile = Profile.objects.create(user=cls.user, emp_type=cls.emp_type)

        cls.leave_counter = LeaveCounter.objects.create(employee=cls.user)

        # Create a placeholder EmployeeType object
        cls.emp_type = EmployeeType.objects.create(name='Test Type')

        # Assign the placeholder EmployeeType to user.profile.emp_type
        cls.user.profile.emp_type = cls.emp_type
        cls.user.profile.save()

    @classmethod
    def tearDownTestData(cls):
        # Reconnect the signal
        post_save.connect(create_profile, sender=User)

    @patch('django.utils.timezone.now')
    def test_reset_counters(self, mock_now):
        # Set the date you want to test
        fake_now = timezone.make_aware(timezone.datetime(2023, 4, 1))
        mock_now.return_value = fake_now

        # Call the method you want to test
        self.leave_counter.reset_counters()

        # Add assertions here to verify the behavior of reset_counters
        # For example, if you expect max_instances_per_quarter to be 6 after the reset:
        self.assertEqual(self.leave_counter.max_instances_per_quarter, 6)


################### REMODEL YOUR USER TYPE FIRST!
