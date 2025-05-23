from django import forms
from .models import LeaveRequest

class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ('leave_type', 'start_date', 'end_date', 'notes', 'form_photo') # 'number_of_days', 
        widgets = {
            'start_date': forms.widgets.DateInput(attrs={'type': 'date'},),
            'end_date': forms.widgets.DateInput(attrs={'type': 'date'},),
            # 'number_of_days': forms.HiddenInput()
        }
        
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remove 'SP' option if the user is not a superuser
        # so only admins can use the special leave option
        if not user.is_superuser:
            # this translates to: display (key, value) for key, value in Leave.LEAVE_TYPES if key is != 'SP'
            # it loops through the choices for the attr and displays all other choices ASIDE FROM 'SP'
            self.fields['leave_type'].choices = [(k, v) for k, v in LeaveRequest.LEAVE_TYPES if k != 'SP']
