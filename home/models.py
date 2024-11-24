from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import Profile
import datetime

### for debugging the additional instance of LeaveCounter when Leave.auto-approve() is called
import logging
logger = logging.getLogger('django')

