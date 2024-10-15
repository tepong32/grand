from django import forms
from .models import Leave

class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = Leave
        fields = ('leave_type', 'date_filed', 'number_of_days', 'notes')

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remove 'SP' option if the user is not a superuser
        # so only admins can use the special leave option
        if not user.is_superuser:
            # this translates to: display (key, value) for key, value in Leave.LEAVE_TYPES if key is != 'SP'
            # it loops through the choices for the attr and displays all other choices ASIDE FROM 'SP'
            self.fields['leave_type'].choices = [(k, v) for k, v in Leave.LEAVE_TYPES if k != 'SP']