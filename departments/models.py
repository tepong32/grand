from django.db import models
from django.conf import settings  # For referencing the User model
from django.utils.text import slugify

class Department(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True, help_text="Unique short code like 'hr', 'gso', 'acctg'")
    description = models.TextField(blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    messenger_link = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='department_images/', blank=True, null=True)
    deptHead_or_oic = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # or to EmployeeProfile if that's the manager base
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments'
    )
    dashboard_view_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Enter the name of the view used for this department's dashboard (e.g., 'hr_dashboard')"
    )
    dashboard_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to the dashboard template, e.g., 'home/authed/dashboards/hr.html'"
        "\nMake sure to include the full path relative to the templates directory and create corresponding templates."
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Override save method to ensure slug is set based on name if not provided.
        """
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)



class Plantilla(models.Model):
    title = models.CharField(max_length=100)
    item_number = models.CharField(max_length=20, blank=True, null=True)  # Optional but useful
    salary_grade = models.PositiveIntegerField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.title}"

