from django.contrib import admin
from .models import Announcement, OrgPersonnel, DepartmentContact


admin.site.register(Announcement)
admin.site.register(OrgPersonnel)
admin.site.register(DepartmentContact)