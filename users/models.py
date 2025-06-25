from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.utils import timezone
from PIL import Image
from django.urls import reverse
from django.utils.text import slugify

from django.core.validators import MinLengthValidator

### for debugging
import logging
logger = logging.getLogger(__name__)


### Documentation: ###
# See: https://docs.djangoproject.com/en/4.2/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project
'''
    If you’re starting a new project, it’s highly recommended to set up a custom user model, even if the default User model is sufficient for you.
    This model behaves identically to the default user model, but you’ll be able to customize it in the future if the need arises.
    Configure users.User to be the model used for the auth application by adding AUTH_USER_MODEL to settings.py:
    AUTH_USER_MODEL='users.User'
'''
# THIS NEEDS TO BE DONE PRIOR TO THE FIRST DB MIGRATION OR YOUR APP WILL FAIL


### for reference, follow-along: https://www.youtube.com/watch?v=mndLkCEiflg

class CustomUserManager(UserManager):
    '''
        Our own UserManager that we will use when using the manage.py file
    '''
    def _create_user(self, username, password, **extra_fields):
        if not username:
            '''check if the user provided a valid username'''
            raise ValueError("Please provide a Username.")

        # email = self.normalize_email(email)
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    '''function used in cmd to create a regular user'''
    def create_user(self, username=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(str(username), password, **extra_fields) #string-ify username to avoid errors on forms when editing it in the future

    '''function used in cmd to create a super user'''
    def create_superuser(self, username=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        # just double-checking the superuser creation meets the required priviledges
        # __( I asked chatGPT what these two if lines are for. XD )__
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    '''
        Custom User model the app will use
        Use AbstractBaseUser for manually creating all attr
        Use AbstractUser to automatically have the defaults (username, email, pw, etc)
    '''
    ### key identifier attributes
    username = models.CharField(max_length=255, unique=True) # change max_length if needed, add min_length/value
    email = models.EmailField(unique=True) # add unique & null field options in production!

    ### misc default User attributes
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)  ############################### <-- disabled user account after registration, SET TO TRUE FOR THE FIRST TIME!
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    ### setting user type for permissions-related queries
    # is_advisor          = models.BooleanField(default=True) ### <-- set default permissions here if needed
    # is_team_leader      = models.BooleanField(default=False)
    # is_operations_manager  = models.BooleanField(default=False)

    ### personal info <-- this should match company records as much as possible
    first_name          = models.CharField(max_length=50, null=True, blank=True)
    middle_name         = models.CharField(max_length=50, null=True, blank=True)
    last_name           = models.CharField(max_length=50, null=True, blank=True)
    ext_name            = models.CharField(max_length=3, blank=True, null=True, verbose_name="Extension")

    objects = CustomUserManager() # set the CustomUserManager() above instead of default UserManager() from django.contrib.auth

    USERNAME_FIELD = "username" # the key identifier of accounts. This was also set on the CustomUserManager() class code
    REQUIRED_FIELDS = [] # ["email", "username", "first_name", "last_name"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = 'Users'
        
    def __str__(self):
        return str(self.username)

    def get_full_name(self):
        parts = [
            str(self.first_name or ''),
            str(self.middle_name or ''),
            str(self.last_name or ''),
            str(self.ext_name or ''),
        ]
        return ' '.join(filter(None, parts)).strip()

