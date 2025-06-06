from django.db import models
from django.conf import settings  # For referencing the User model

class Department(models.Model):
    name = models.CharField(max_length=100)
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

    def __str__(self):
        return self.name


class Plantilla(models.Model):
    title = models.CharField(max_length=100)
    item_number = models.CharField(max_length=20, blank=True, null=True)  # Optional but useful
    salary_grade = models.PositiveIntegerField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.title} (SG {self.salary_grade})"

