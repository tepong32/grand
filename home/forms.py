from django import forms
from django.forms import SelectDateWidget
from django.core.exceptions import ValidationError
from .models import Leave, LeaveCounter
from users.models import User


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.staff_id}"

class LeaveForm(forms.ModelForm):
    '''
        This form validates if the user can still apply for Leaves and raises errors if they've already used-up
        or is about to exceed the allowed_instances per quarter or per year.
    '''
    start_date = forms.SelectDateWidget()
    end_date = forms.SelectDateWidget()
    
    class Meta:
        model = Leave
        fields = ['leave_type', 'start_date', 'end_date', 'note']

    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        leave_counter, created = LeaveCounter.objects.get_or_create(employee=self.employee)
        
        if start_date and end_date:
            leave_duration = (end_date - start_date).days + 1

            if leave_counter.instances_used_this_year + leave_duration > leave_counter.max_instances_per_year:
                raise ValidationError("You have reached or are about to exceed the allowed instances per year. \nPlease coordinate with your immediate supervisor if you need adjustments.")

            if leave_counter.instances_used_this_quarter + leave_duration > leave_counter.max_instances_per_quarter:
                raise ValidationError("You have reached or are about to exceed the allowed instances per quarter. \nPlease coordinate with your immediate supervisor if you need adjustments.")

        return cleaned_data

    def save(self, commit=True):
        # Call the original save method
        leave = super().save(commit=False)

        # Call the auto_approve method to check if there are still allowed leaves for the day
        leave.auto_approve()

        # Commit the changes if specified
        if commit:
            leave.save()

        return leave


class IncreaseMaxInstancesForm(forms.Form):
    ''' See utils.py '''
    year_additional_instances = forms.IntegerField()
    quarter_additional_instances = forms.IntegerField()