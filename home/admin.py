from django.contrib import admin
from .models import Announcement, OrgPersonnel, DepartmentContact, DownloadableForm



@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'user')

@admin.register(OrgPersonnel)
class OrgPersonnelAdmin(admin.ModelAdmin):
    list_display = ('title', 'name', 'display_order')

@admin.register(DepartmentContact)
class DepartmentContactAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(DownloadableForm)
class DownloadableFormAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_on')

###the traditional way of registering models to admin
# admin.site.register(Announcement)
# admin.site.register(OrgPersonnel)
# admin.site.register(DepartmentContact)