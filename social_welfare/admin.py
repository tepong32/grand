from django.contrib import admin

from .models import ProgramActivity, SocialWelfareProgram


@admin.register(SocialWelfareProgram)
class SocialWelfareProgramAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "program_type", "department", "status", "updated_at")
    list_filter = ("department", "program_type", "status")
    search_fields = ("code", "name", "description")


@admin.register(ProgramActivity)
class ProgramActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "program", "starts_at", "venue", "status", "actual_attendance")
    list_filter = ("activity_type", "status", "starts_at")
    search_fields = ("title", "program__name", "venue")
