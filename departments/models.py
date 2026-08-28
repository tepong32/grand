from django.db import models
from django.conf import settings  # For referencing the User model
from django.utils.text import slugify
from django.core.exceptions import ValidationError
import re


class DepartmentDefaults:
    """Centralized Department app constants."""
    DASHBOARD_TEMPLATE_FALLBACK = "home/authed/dashboards/generic.html"
    DEPT_SLUG_PREFIX_LENGTH = 120

class Department(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True, help_text="Unique short code like 'hr', 'gso', 'acctg'")
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
    dashboard_view_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Enter the name of the view used for this department's dashboard (e.g., 'hr_dashboard')"
    )
    dashboard_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to the dashboard template, e.g., 'home/authed/dashboards/hr.html'"
        "\nMake sure to include the full path relative to the templates directory and create corresponding templates."
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Override save method to ensure slug is set based on name if not provided.
        """
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_dashboard_template(self):
        """
        Return fallback-safe dashboard template path for this department.
        """
        return self.dashboard_template or DepartmentDefaults.DASHBOARD_TEMPLATE_FALLBACK

    def dashboard_context(self, user):
        """
        Return department-specific dashboard context.
        """
        from .services.dashboard_service import get_department_home_context
        return get_department_home_context(self, user)



class Plantilla(models.Model):
    title = models.CharField(max_length=100)
    item_number = models.CharField(max_length=20, blank=True, null=True)  # Optional but useful
    salary_grade = models.PositiveIntegerField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.title}"


class InternalHowTo(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"
    STATUS_CHOICES = ((DRAFT, "Draft"), (PUBLISHED, "Published"), (RETIRED, "Retired"))

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="internal_how_tos")
    slug = models.SlugField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=180)
    summary = models.TextField()
    required_permission = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional app_label.codename. Leave blank for every employee currently assigned to this department.",
    )
    page_patterns = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional named-route patterns such as accounting:opening_*; blank makes the guide department-wide.",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT)
    sort_order = models.PositiveSmallIntegerField(default=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_internal_how_tos",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="updated_internal_how_tos",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "title", "-version")
        constraints = (
            models.UniqueConstraint(fields=("department", "slug", "version"), name="unique_internal_howto_version"),
            models.UniqueConstraint(
                fields=("department", "slug"),
                condition=models.Q(status="published"),
                name="unique_published_internal_howto",
            ),
        )
        permissions = (("manage_internal_how_tos", "Can manage department internal how-to guides"),)

    def __str__(self):
        return f"{self.department}: {self.title} v{self.version}"

    def clean(self):
        if self.required_permission and not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", self.required_permission):
            raise ValidationError({"required_permission": "Use an app_label.codename permission identifier."})
        if not isinstance(self.page_patterns, list) or any(
            not isinstance(value, str) or not value.strip() for value in self.page_patterns
        ):
            raise ValidationError({"page_patterns": "Use a list of non-empty named-route patterns."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status in (self.PUBLISHED, self.RETIRED):
                governed = (
                    "department_id", "slug", "version", "title", "summary",
                    "required_permission", "page_patterns", "sort_order",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Published guide content is immutable. Retire it and publish a new version.")
            if prior and prior.status == self.PUBLISHED and self.status not in (self.PUBLISHED, self.RETIRED):
                raise ValidationError("A published guide can only remain published or be retired.")
            if prior and prior.status == self.RETIRED and self.status != self.RETIRED:
                raise ValidationError("A retired guide cannot be republished. Create a new version.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.status == self.PUBLISHED and (not self.pk or not self.steps.exists()):
            raise ValidationError("Add at least one reviewed step before publishing the guide.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Internal how-to history is retained. Retire the guide instead of deleting it.")


class InternalHowToStep(models.Model):
    how_to = models.ForeignKey(InternalHowTo, on_delete=models.PROTECT, related_name="steps")
    position = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=180)
    instruction = models.TextField()
    expected_result = models.TextField(blank=True)
    caution = models.TextField(blank=True)
    action_label = models.CharField(max_length=80, blank=True)
    action_route_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional named URL without arguments, for example accounting:opening_workspace.",
    )

    class Meta:
        ordering = ("position", "pk")
        constraints = (
            models.UniqueConstraint(fields=("how_to", "position"), name="unique_internal_howto_step_position"),
        )

    def __str__(self):
        return f"{self.how_to.title}: {self.position}. {self.title}"

    def save(self, *args, **kwargs):
        if self.how_to_id and self.how_to.status in (InternalHowTo.PUBLISHED, InternalHowTo.RETIRED):
            raise ValidationError("Published guide steps are immutable. Create a new guide version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.how_to.status in (InternalHowTo.PUBLISHED, InternalHowTo.RETIRED):
            raise ValidationError("Published guide steps are immutable. Retire the guide instead.")
        return super().delete(*args, **kwargs)


class InternalHowToStepCompletion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="internal_howto_step_completions",
    )
    step = models.ForeignKey(InternalHowToStep, on_delete=models.PROTECT, related_name="completions")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="internal_howto_completions")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("completed_at", "pk")
        constraints = (
            models.UniqueConstraint(fields=("user", "step"), name="unique_user_internal_howto_step"),
        )

    def clean(self):
        if self.step_id and self.department_id != self.step.how_to.department_id:
            raise ValidationError({"department": "The completion snapshot must match the guide department."})

    def __str__(self):
        return f"{self.user}: {self.step}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

