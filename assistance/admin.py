from django.contrib import admin
from .models import AssistanceType, AssistanceRequest


@admin.register(AssistanceType)
class AssistanceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(AssistanceRequest)
class AssistanceRequestAdmin(admin.ModelAdmin):
    list_display = (
        'reference_code', 
        'full_name', 
        'assistance_type', 
        'status', 
        'submitted_at',
        'is_active',
    )
    list_filter = ('status', 'assistance_type', 'is_active', 'submitted_at')
    search_fields = ('reference_code', 'full_name', 'email', 'phone')
    readonly_fields = ('reference_code', 'submitted_at')
    ordering = ('-submitted_at',)

    def get_queryset(self, request):
        """Override default queryset to hide soft-deleted entries from regular view."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superusers see all
        return qs.filter(is_active=True)

    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for superusers."""
        return request.user.is_superuser

    actions = ['mark_inactive']

    @admin.action(description="Archive selected requests (Soft Delete)")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} request(s) archived successfully.")
