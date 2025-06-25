from django.contrib import admin
from .models import EmployeeProfile, CitizenProfile, ProfileEditLog
# Register your models here.
admin.site.register(EmployeeProfile)
admin.site.register(CitizenProfile)

@admin.register(ProfileEditLog)
class ProfileEditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'edited_by', 'profile_type', 'section', 'timestamp')
    search_fields = ('user__username', 'edited_by__username', 'note')
    list_filter = ('profile_type', 'timestamp')
