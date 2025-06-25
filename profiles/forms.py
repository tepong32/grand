from django import forms
from .models import EmployeeProfile, CitizenProfile

class ProfileUpdateForm(forms.ModelForm):
	class Meta:
		model = EmployeeProfile
		fields = ["profile_image", "note", "contact_number", "address"] # attrs editable by the user, others are for HR/admin edits only


class CitizenProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CitizenProfile
        fields = ['contact_number', 'address']