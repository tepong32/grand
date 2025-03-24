from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.utils import timezone
from PIL import Image
from django.urls import reverse
from django.utils.text import slugify


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinLengthValidator, MaxLengthValidator

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
    first_name          = models.CharField(max_length=50)
    middle_name         = models.CharField(max_length=50, blank=True)
    last_name           = models.CharField(max_length=50)
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
        if self.ext_name != None:
            return str(self.first_name)+' '+self.middle_name + ' ' +self.last_name + ' ' + self.ext_name
        elif self.first_name and self.last_name:
            return str(self.first_name)+' '+self.middle_name + ' ' + self.last_name
        else:
            return str(self.username)


class Manager(models.Model):
    '''
    Linked to Department as dropdown
    '''
    name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.name}'


class Department(models.Model):
    '''
    Linked to Profile as dropdown
    '''
    select      = "---select one---"
    ACCTG       = "Accounting Office"
    AGRI        = "Agriculture Office"
    BPLO        = "Business Processes & Licensing Office"
    CSU         = "Civil Security Unit"
    GSO         = "General Services Office"
    HR          = "Human Resources"
    LCR         = "Local Civil Registrar\'s Office"
    MA          = "Municipal Administrator\'s Office"
    MENRO       = "Environment & Natural Resources Office"
    MO          = "Mayor\'s Office"
    MPDO        = "Municipal Planning & Development Office"
    MSWD        = "Social Welfare & Development"
    MTO         = "Treasurer\'s Office"
    NUTRI       = "Nutrition Office"
    OSCA        = "Senior Citizen Affairs"
    SB          = "Sangguniang Bayan Office"
    
    choices = [
        (select, "select"),
        (ACCTG, "ACCTG"),
        (AGRI, "AGRI"), 
        (BPLO, "BPLO"),
        (CSU, "CSU"),
        (GSO, "GSO"),
        (HR, "HR"),
        (LCR, "LCR"),
        (MA, "MA"),
        (MENRO, "MENRO"),
        (MO, "MO"),
        (MPDO, "MPDO"),
        (MSWD, "MSWD"),
        (MTO, "MTO"),
        (NUTRI, "NUTRI"),
        (OSCA, "OSCA"),
        (SB, "SB")
        ]

    name = models.CharField(blank=True, null=False, max_length=80, choices=choices, default=select, verbose_name="Department: ")
    manager = models.ForeignKey(Manager, on_delete=models.SET_NULL, null=True, blank=False)

    def __str__(self):
        return f"{self.name}".strip()


class RegOrCT_Salary(models.Model):
    """
    Salary setup for Regular and Co-Terminus Employees.
    Manual setup for each SG+Step since not all will be used.
    See Official Gazette for reference.
    """
    grade = models.PositiveIntegerField(null=True)
    step = models.PositiveIntegerField(default=0, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    class Meta:
        verbose_name = "RegOrCT Salary"
        verbose_name_plural = "RegOrCT Salaries"
        unique_together = ('grade', 'step')

    def __str__(self):
        return f"Grade {self.grade}-({self.step}): {self.amount}"


class JO_Salary(models.Model):
    """
    Salary setup for Job Order Employees.
    Daily rate setup.
    """
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    class Meta:
        verbose_name = "JO Salary"
        verbose_name_plural = "JO Salaries"

    def __str__(self):
        return f"Daily rate: {self.daily_rate}"


class EmployeeProfile(models.Model):
    """
    Profile model for additional user information.
    Only intended for HR use. Overly-sensitive information should not be stored here/displayed to other users.
    """
    user            = models.OneToOneField(User, on_delete=models.CASCADE)
    contact_number  = models.CharField(max_length=11, null=True, blank=False,
                    validators=[MinLengthValidator(10)],
                    verbose_name="Contact Number") # intended only for HR use, will not be displayed to other users
    address         = models.CharField(max_length=255, null=True, blank=False)
    note            = models.CharField(max_length=255, null=True, blank=True) # personal short note to other users

    select  = "---select one---"
    REG     = "Regular Employee"
    CT      = "Co-Terminus Employee"
    JO      = "Job Order Employee"
    employment_type_choices = [
        (select, "select"),
        (REG, "REG"),
        (CT, "CT"),
        (JO, "JO")
    ]
    employment_type = models.CharField(blank=True, null=False, max_length=80, choices=employment_type_choices, default=select)
    designation     = models.CharField(max_length=255, null=True, blank=False)
    department      = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=False)
    reg_or_ct_salary = models.ForeignKey(RegOrCT_Salary, on_delete=models.SET_NULL, null=True, blank=True) # can be left blank on edits
    jo_salary = models.ForeignKey(JO_Salary, on_delete=models.SET_NULL, null=True, blank=True) # can be left blank on edits
    

    def dp_directory_path(instance, filename):
        # file will be uploaded to MEDIA_ROOT/DP/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
        return 'users/{}/DP/{}'.format(instance.user.username, filename)
    image           = models.ImageField(default='defaults/default_user_dp.png', blank=True, upload_to=dp_directory_path, verbose_name="Profile Image ")
    slug            = models.SlugField(default='', blank=True)

    def __str__(self):
        return f"{self.user.username}"

    def get_salary(self):
        if self.employment_type in [self.REG, self.CT]:  # Regular or Co-Terminus
            if self.reg_or_ct_salary:
                return self.reg_or_ct_salary.amount
            else:
                return int(0)  # or return a default value
        elif self.employment_type == self.JO:  # Job Order
            if self.jo_salary:
                return self.jo_salary.daily_rate  # Adjust as necessary for daily calculations
            else:
                return int(0)  # or return a default value
        return int(0)  # or return a default value

    def get_absolute_url(self):
        return reverse('profile', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):        # for resizing/downsizing images
        if not self.slug:
            base_slug = slugify(self.user.username)
            slug = base_slug
            counter = 1
            while EmployeeProfile.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super(EmployeeProfile, self).save(*args, **kwargs)
        logger.info("Profile saved.")

        img = Image.open(self.image.path)   # open the image of the current instance
        if img.height > 600 or img.width > 600: # for sizing-down the images to conserve memory in the server
            output_size = (600, 600)
            img.thumbnail(output_size)
            img.save(self.image.path)
