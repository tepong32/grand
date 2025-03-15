from django.contrib import admin
from .models import Announcement, OrgPersonnel, DepartmentContact



@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title',)

@admin.register(OrgPersonnel)
class OrgPersonnelAdmin(admin.ModelAdmin):
    list_display = ('title',)

@admin.register(DepartmentContact)
class DepartmentContactAdmin(admin.ModelAdmin):
    list_display = ('name',)


###the traditional way of registering models to admin
# admin.site.register(Announcement)
# admin.site.register(OrgPersonnel)
# admin.site.register(DepartmentContact)