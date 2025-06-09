from django.db import models
from django.contrib import admin
from .models import AssistanceType, AssistanceRequest, RequestDocument
from users.models import User 


class RequestLog(models.Model):
    request = models.ForeignKey('AssistanceRequest', on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status_before = models.CharField(max_length=20)
    status_after = models.CharField(max_length=20)
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.request.reference_code} update on {self.timestamp:%Y-%m-%d %H:%M}"


class RequestDocumentInline(admin.TabularInline):
    model = RequestDocument
    readonly_fields = ('uploaded_at',)


class RequestLogInline(admin.TabularInline):
    model = RequestLog
    readonly_fields = ('timestamp', 'updated_by', 'status_before', 'status_after', 'remarks')
    extra = 0
    can_delete = False


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
        'edit_code',
        'full_name', 
        'assistance_type', 
        'status', 
        'submitted_at',
        'is_active',
    )
    # list_filter = ('status', 'assistance_type', 'is_active', 'submitted_at')
    search_fields = ('reference_code', 'full_name', 'email', 'phone')
    readonly_fields = ('reference_code', 'submitted_at')
    ordering = ('-submitted_at',)
    inlines = [RequestLogInline, RequestDocumentInline]

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
    
    def save_model(self, request, obj, form, change):
        if change:
            # Log only if status or remarks changed
            orig = AssistanceRequest.objects.get(pk=obj.pk)
            if orig.status != obj.status or orig.remarks != obj.remarks:
                RequestLog.objects.create(
                    request=obj,
                    updated_by=request.user,
                    status_before=orig.status,
                    status_after=obj.status,
                    remarks=obj.remarks
                )
        super().save_model(request, obj, form, change)

    
