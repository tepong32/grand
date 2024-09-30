from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.utils import timezone
from PIL import Image
from django.urls import reverse
from django.utils.text import slugify


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinLengthValidator, MaxLengthValidator


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
    # is_advisor          = models.BooleanField(default=True) ### <-- default is all users that register are advisors
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
        return str(self.first_name)+' '+self.middle_name + ' ' +self.last_name


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

    class Meta:
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.name}".strip()


def validate_salary_grade(value):
    if value < 1 or value > 27:
        raise ValidationError('Salary grade must be between 1 and 27.')

def validate_salary_grade_step(value):
    if value < 0 or value > 8:
        raise ValidationError('Salary grade step must be between 0 and 8.')


class Designation(models.Model):
    '''
    Linked to Profile as dropdown
    Will have their own salary_grade & _step so addt'l items can just be selected by admins and the system
        will auto-compute the salary.
    Only admins can modify user details. Updating profile on users' end will not show the SG and SGS fields

    '''
    # take note: salary_grade and step fields
    # it should ONLY be visible to the owner and admins
    name = models.CharField(max_length=255, null=True, blank=False)
    salary_grade = models.PositiveIntegerField(default=1,
        validators=[validate_salary_grade],
        verbose_name="Salary Grade"
    )
    salary_grade_step = models.PositiveIntegerField(
        default=0,
        validators=[validate_salary_grade_step],
        verbose_name="Salary Grade Step",
        blank=True,
        help_text="Only visible to you or Administrators."
    )

    def get_salary_amount(self):
        try:
            salary = Salary.objects.get(grade=self.salary_grade, step=self.salary_grade_step)
            print(f"Found Salary: Grade {self.salary_grade}, Step {self.salary_grade_step}, Amount {salary.amount}")
            return salary.amount
        except Salary.DoesNotExist:
            print(f"Salary not found for Grade {self.salary_grade}, Step {self.salary_grade_step}")
            return 0.00

    def __str__(self):
        return f"{self.name}".strip().title() + " / SG " + f"{self.salary_grade}" +"-" + f"{self.salary_grade_step}"




class Profile(models.Model):
    user            = models.OneToOneField(User, on_delete=models.CASCADE)
    contact_number  = models.CharField(max_length=11, null=True, blank=False,
                    validators=[MinLengthValidator(10)],
                    verbose_name="Contact Number")
    address         = models.CharField(max_length=255, null=True, blank=False)
    designation     = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=False)
    department      = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=False)
    slug            = models.SlugField(default='', blank=True)

    def dp_directory_path(instance, filename):
        # file will be uploaded to MEDIA_ROOT/DP/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
        return 'users/{}/DP/{}'.format(instance.user.username, filename)
    image = models.ImageField(default='defaults/default_user_dp.png', blank=True, upload_to=dp_directory_path, verbose_name="Profile Picture: ")

    

    def __str__(self):
        return f"{self.user.username}"

    def get_absolute_url(self):
        return reverse('profile', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):        # for resizing/downsizing images
        if not self.slug:
            base_slug = slugify(self.user.username)
            slug = base_slug
            counter = 1
            while Profile.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super(Profile, self).save(*args, **kwargs)

        img = Image.open(self.image.path)   # open the image of the current instance
        if img.height > 600 or img.width > 600: # for sizing-down the images to conserve memory in the server
            output_size = (600, 600)
            img.thumbnail(output_size)
            img.save(self.image.path)


class Salary(models.Model):
    grade = models.PositiveIntegerField(null=True)
    step = models.PositiveIntegerField(default=0, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    class Meta:
        verbose_name_plural = "Salaries"
        unique_together = ('grade', 'step')

    def __str__(self):
        return f"Grade {self.grade} - Step {self.step}: {self.amount}"

class SalaryIncrement(models.Model):        ### parang hindi na to kailangan?
    grade = models.PositiveIntegerField()
    step = models.PositiveIntegerField()
    increment = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('grade', 'step')
        verbose_name_plural = "Salary Increments"

    def __str__(self):
        return f"Grade {self.grade} - Step {self.step}: Increment {self.increment}"


@receiver(post_save, sender=Profile)
def update_salary_on_profile_save(sender, instance, **kwargs):
    update_salary(instance.designation.salary_grade, instance.designation.salary_grade_step)


def update_salary(grade, step):
    base_salaries = {}
    increments = {}

    base_salary = base_salaries.get(grade, 0)
    try:
        increment = SalaryIncrement.objects.get(grade=grade, step=step).increment
    except SalaryIncrement.DoesNotExist:
        increment = 0

    new_salary_amount = base_salary + increment

    salary, created = Salary.objects.update_or_create(
        grade=grade,
        step=step,
        defaults={'amount': new_salary_amount}
    )

    return salary


################### set up all salary grades here



############################ LEAVES