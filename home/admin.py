from django.contrib import admin
from .models import (
    Announcement,
    DepartmentContact,
    DownloadableForm,
    OrgPersonnel,
    ServiceShortcut,
    SiteConfiguration,
)



@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'user')

@admin.register(OrgPersonnel)
class OrgPersonnelAdmin(admin.ModelAdmin):
    list_display = ('title', 'name', 'display_order')

@admin.register(DepartmentContact)
class DepartmentContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'landline', 'mobile', 'email', 'messenger_chat_link')


@admin.register(DownloadableForm)
class DownloadableFormAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_on')


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Institutional identity", {"fields": ("brand_name", "institution_name", "portal_label", "tagline")}),
        ("Homepage", {"fields": ("hero_heading", "hero_text", "logo", "hero_image", "featured_media_url", "featured_media_title")}),
        ("Appearance", {"fields": ("primary_color", "accent_color")}),
        ("Footer", {"fields": ("contact_email", "footer_note")}),
    )

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServiceShortcut)
class ServiceShortcutAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "display_order", "is_featured", "is_active")
    list_editable = ("display_order", "is_featured", "is_active")
    list_filter = ("audience", "is_active", "is_featured")

###the traditional way of registering models to admin
# admin.site.register(Announcement)
# admin.site.register(OrgPersonnel)
# admin.site.register(DepartmentContact)
