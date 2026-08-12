from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
import logging

from profiles.models import EmployeeProfile


# Logger setup
logger = logging.getLogger(__name__)


class AccrualModel(models.Model):
    accrual_value = models.DecimalField(max_digits=4, decimal_places=2, default=1.2, help_text="This defaults to 1.2 per month.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SL_Accrual(AccrualModel):
    '''
    Assign values here if the default (1.2) does not fit your needs.
    Useful if the changes will be made in the admin UI instead of the codebase.
    '''

    class Meta:
        verbose_name = "SL Accrual"
        verbose_name_plural = "SL Accruals"
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_sl_accrual')
        ]


class VL_Accrual(AccrualModel):
    '''
    Assign values here if the default (1.2) does not fit your needs.
    Useful if the changes will be made in the admin UI instead of the codebase.
    '''

    class Meta:
        verbose_name = "VL Accrual"
        verbose_name_plural = "VL Accruals"
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_vl_accrual')
        ]


class LeavePolicy(models.Model):
    """Editable policy values used by automated accrual and leave validation."""

    name = models.CharField(max_length=100, default="Standard leave policy")
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField()
    monthly_sick_accrual = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.20, validators=[MinValueValidator(0)]
    )
    monthly_vacation_accrual = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.20, validators=[MinValueValidator(0)]
    )
    special_leave_annual_allocation = models.DecimalField(
        max_digits=5, decimal_places=2, default=10, validators=[MinValueValidator(0)]
    )
    minimum_request_increment = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.50,
        validators=[MinValueValidator(0.50)],
        help_text="Smallest leave unit employees may request. Grand's UI supports 0.5 or 1 day.",
    )
    sick_carryover_cap = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    vacation_carryover_cap = models.DecimalField(
        max_digits=6, decimal_places=2, default=20, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_policies_created',
    )

    class Meta:
        ordering = ["-effective_from", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="one_active_leave_policy",
            )
        ]
        permissions = [
            ("manage_leave_credits", "Can manage leave policies and credit adjustments"),
        ]

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"


class LeaveCredit(models.Model):
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE)

    # Current Year Credits
    current_year_sl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_vl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_special_credits = models.DecimalField(max_digits=5, decimal_places=2, default=10) # not being handled yet

    # Total Accumulated Credits (including carry-over)
    sl_credits_from_prev_yr = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vl_credits_from_prev_yr = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Boolean flag to check if user already accrued leave credits this month
    credits_accrued_this_month = models.BooleanField(default=False)

    def __str__(self):
        display_name = self.employee.user.get_full_name() or self.employee.user.username
        return f"{display_name}'s Leave Credits"

    @property
    def total_sl_credits(self):
        return self.current_year_sl_credits + self.sl_credits_from_prev_yr

    @property
    def total_vl_credits(self):
        return self.current_year_vl_credits + self.vl_credits_from_prev_yr

    @classmethod
    def reset_accrual_flags(cls):
        """
        Resets the credits_accrued_this_month flags for all leave credits.
        """
        from .services.credit_service import reset_accrual_flags

        logger.info("Resetting credits_accrued_this_month flags to False.")
        reset_count = reset_accrual_flags(cls)
        logger.info("Reset monthly accrual flag to False for %s rows.", reset_count)
        return reset_count

    def carry_over_credits(self):
        """
        Carries over un-used Leave credits from the current year to credits_from_prev_yr.
        """
        from .services.credit_service import carry_over_leave_instance
        return carry_over_leave_instance(self)

    @classmethod
    def carry_over_unused_credits(cls):
        """
        Carries over unused leave credits for all employees.
        """
        from .services.credit_service import carry_over_unused_credits

        count = carry_over_unused_credits(cls)
        logger.info("carry_over_unused_credits() triggered. Carried over unused credits for %s employees.", count)
        return count

    @classmethod
    def get_accrual_value(cls, accrual_model, default_value):
        """
        Fetches the accrual value from the model or returns a default value if not found.
        """
        from .services.credit_service import get_accrual_value

        return get_accrual_value(accrual_model, default_value)

    @classmethod
    def accrue_all_leave_credits(cls):
        """
        Accrues leave credits based on the defined accrual models or a default value.
        """
        from .services.credit_service import accrue_all_leave_credits

        logger.info("Starting monthly leave credit accrual...")
        return accrue_all_leave_credits(cls, SL_Accrual, VL_Accrual)

    @classmethod
    def update_leave_credits(cls):
        """
        Scheduled/manual refresh that handles monthly accruals and annual carry-over.
        """
        from .services.credit_service import update_leave_credits

        logger.info("update_leave_credits(cls): Updating leave credits...")
        # Keep behavior aligned with previous implementation: carry over only on Jan 1st.
        return update_leave_credits(cls, SL_Accrual, VL_Accrual, from_cron=False)


def leave_form_directory_path(instance, filename):
    # Leave > LeaveCredits > Profile > User > username
    username = instance.employee.employee.user.username
    return 'users/{}/leaveForms/{}'.format(username, filename)


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('SL', 'Sick Leave'),
        ('VL', 'Vacation Leave'),
        ('SP', 'Special Leave'),
    ]

    STATUS_OPTIONS = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    DAY_PORTIONS = [
        ('FULL', 'Full day'),
        ('AM', 'Morning half-day'),
        ('PM', 'Afternoon half-day'),
    ]

    employee = models.ForeignKey(LeaveCredit, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=2, choices=LEAVE_TYPES)
    date_filed = models.DateField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=False)
    end_date = models.DateField(null=True, blank=False)
    day_portion = models.CharField(max_length=4, choices=DAY_PORTIONS, default='FULL')
    number_of_days = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_OPTIONS, default='PENDING')
    notes = models.TextField(null=True, blank=True)
    form_photo = models.ImageField(null=True, blank=True, upload_to=leave_form_directory_path, verbose_name="Form Photo (w/ Signatures): ")

    class Meta:
        ordering = ['-date_filed']

    def __str__(self):
        return f"{self.employee.employee.user.get_full_name()} - {self.leave_type} - {self.date_filed}"

    def get_absolute_url(self):
        return reverse('leave_detail', kwargs={'pk': self.pk})

    def clean(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start date cannot be greater than end date.")
        else:
            raise ValidationError("Both start date and end date are required.")

        if self.employee:
            from .services.request_service import has_request_conflict
            if self.status != 'CANCELLED' and has_request_conflict(
                self.employee,
                self.start_date,
                self.end_date,
                exclude_pk=self.pk,
            ):
                raise ValidationError("A leave request already exists for this date range.")

        if self.day_portion != 'FULL' and self.start_date != self.end_date:
            raise ValidationError("Half-day leave must start and end on the same working day.")

    def save(self, *args, **kwargs):
        self.number_of_days = self.calculate_number_of_days()

        old_status = None
        old_leave_type = None
        old_number_of_days = None

        if self.pk:
            old_instance = LeaveRequest.objects.get(pk=self.pk)
            if old_instance.employee_id != self.employee_id:
                raise ValidationError("A leave request cannot be reassigned to another employee.")
            old_status = old_instance.status
            old_leave_type = old_instance.leave_type
            old_number_of_days = old_instance.number_of_days

        with transaction.atomic():
            super().save(*args, **kwargs)

            from .services.request_service import sync_leave_credit_for_status_change
            sync_leave_credit_for_status_change(
                self,
                old_status=old_status,
                old_leave_type=old_leave_type,
                old_number_of_days=old_number_of_days,
            )

    def calculate_number_of_days(self):
        from .services.request_service import calculate_request_days
        return calculate_request_days(self.start_date, self.end_date, self.day_portion)

    def get_remaining_leave_credits(self):
        """
        Calculates the remaining leave credits for the employee based on the leave request's status and type.
        """
        if self.status == 'APPROVED':
            if self.leave_type == 'SL':
                return self.employee.total_sl_credits
            elif self.leave_type == 'VL':
                return self.employee.total_vl_credits
            return self.employee.current_year_special_credits
        # Handle special leave credits if applicable
        else:
            pending_days = LeaveRequest.objects.filter(
                employee=self.employee,
                status='PENDING',
                leave_type=self.leave_type
            ).aggregate(total=models.Sum('number_of_days'))['total'] or 0
            if self.leave_type == 'SL':
                return f"{self.employee.total_sl_credits} - {pending_days} (pending)"
            elif self.leave_type == 'VL':
                return f"{self.employee.total_vl_credits} - {pending_days} (pending)"
            # Handle special leave credits if applicable
            elif self.leave_type == 'SP':
                return f"{self.employee.current_year_special_credits} - {pending_days} (pending)"


class LeaveCreditLog(models.Model):
    action_date = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=50)  # e.g., 'Monthly Accrual', 'Yearly Carry Over'
    leave_credits = models.ForeignKey(LeaveCredit, on_delete=models.CASCADE, related_name='logs')

    def __str__(self):
        return f"{self.action_type} completed."


class LeaveCreditTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('ACCRUAL', 'Automatic accrual'),
        ('ADJUSTMENT', 'Manual adjustment'),
        ('DEDUCTION', 'Approved leave deduction'),
        ('REVERSAL', 'Reversal'),
        ('CARRYOVER', 'Yearly carry-over'),
    ]

    leave_credit = models.ForeignKey(
        LeaveCredit, on_delete=models.CASCADE, related_name='transactions'
    )
    leave_type = models.CharField(max_length=2, choices=LeaveRequest.LEAVE_TYPES)
    transaction_type = models.CharField(max_length=12, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=7, decimal_places=2)
    current_delta = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    carried_delta = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=7, decimal_places=2)
    period = models.DateField(null=True, blank=True, help_text="First day of an automatic accrual month.")
    policy = models.ForeignKey(LeavePolicy, on_delete=models.SET_NULL, null=True, blank=True)
    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_transactions'
    )
    reversal_of = models.OneToOneField(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversal'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['leave_credit', 'leave_type', 'transaction_type', 'period'],
                condition=Q(transaction_type='ACCRUAL', period__isnull=False),
                name='unique_monthly_leave_accrual',
            ),
            models.UniqueConstraint(
                fields=['leave_credit', 'leave_type', 'transaction_type', 'period'],
                condition=Q(transaction_type='CARRYOVER', period__isnull=False),
                name='unique_yearly_leave_carryover',
            ),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()}: {self.amount:+} {self.leave_type}"


# Backward-compatible alias retained for existing imports/tests.
LeaveCredits = LeaveCredit
