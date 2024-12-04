from django.test import TestCase
from django.db.models.signals import post_save
from unittest.mock import patch
from django.utils import timezone
from leave_mgt.models import LeaveCredits, LeaveRequest
from users.models import User

