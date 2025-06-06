from django.contrib import admin
from .models import EmployeeProfile, CitizenProfile
# Register your models here.
admin.site.register(EmployeeProfile)
admin.site.register(CitizenProfile)