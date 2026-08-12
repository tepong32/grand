from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import LeaveCredit, LeavePolicy, LeaveRequest

class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ('leave_type', 'start_date', 'end_date', 'day_portion', 'notes', 'form_photo')
        widgets = {
            'start_date': forms.widgets.DateInput(attrs={'type': 'date'},),
            'end_date': forms.widgets.DateInput(attrs={'type': 'date'},),
        }
        
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remove 'SP' option if the user is not a superuser
        # so only admins can use the special leave option
        if not user.is_superuser:
            # this translates to: display (key, value) for key, value in Leave.LEAVE_TYPES if key is != 'SP'
            # it loops through the choices for the attr and displays all other choices ASIDE FROM 'SP'
            self.fields['leave_type'].choices = [(k, v) for k, v in LeaveRequest.LEAVE_TYPES if k != 'SP']
        from .services.credit_service import get_active_policy
        policy = get_active_policy()
        if policy and policy.minimum_request_increment >= Decimal('1.00'):
            self.fields['day_portion'].choices = [('FULL', 'Full day')]

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        day_portion = cleaned.get('day_portion')
        if day_portion in ('AM', 'PM') and start_date and end_date and start_date != end_date:
            raise ValidationError("Morning and afternoon half-days must use the same start and end date.")
        return cleaned


class LeavePolicyForm(forms.ModelForm):
    class Meta:
        model = LeavePolicy
        fields = (
            'name', 'effective_from', 'monthly_sick_accrual',
            'monthly_vacation_accrual', 'special_leave_annual_allocation',
            'minimum_request_increment', 'sick_carryover_cap',
            'vacation_carryover_cap',
        )
        widgets = {'effective_from': forms.DateInput(attrs={'type': 'date'})}

    def clean_minimum_request_increment(self):
        value = self.cleaned_data['minimum_request_increment']
        if value not in (Decimal('0.50'), Decimal('1.00')):
            raise ValidationError("Grand currently supports a minimum request increment of 0.5 or 1 day.")
        return value


class LeaveCreditAdjustmentForm(forms.Form):
    leave_credit = forms.ModelChoiceField(
        queryset=LeaveCredit.objects.none(), label='Employee'
    )
    leave_type = forms.ChoiceField(choices=LeaveRequest.LEAVE_TYPES)
    amount = forms.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Use a positive amount to grant credits or a negative amount to subtract them.",
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), min_length=5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['leave_credit'].queryset = LeaveCredit.objects.select_related(
            'employee__user'
        ).order_by('employee__user__last_name', 'employee__user__username')
