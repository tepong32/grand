from django import forms
from .models import EmployeeProfile, CitizenProfile

class ProfileUpdateForm(forms.ModelForm):
	class Meta:
		model = EmployeeProfile
		fields = ["profile_image", "note", "contact_number", "address"] # attrs editable by the user, others are for HR/admin edits only

class EmploymentProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            'assigned_department',
            'plantilla',
            'employment_type',
            'position_title',
            'salary_grade',
            'step_increment',
            'tin',
            'gsis_id',
            'pagibig_id',
            'philhealth_id',
            'sss_id',
            'jo_date_hired',
            'reg_date_hired',
            'assigned_department_memo',
        ]
        widgets = {
            'assigned_department': forms.Select(attrs={'class': 'form-control'}),
            'plantilla': forms.Select(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'position_title': forms.TextInput(attrs={'class': 'form-control'}),
            'salary_grade': forms.TextInput(attrs={'class': 'form-control'}),
            'step_increment': forms.NumberInput(attrs={'class': 'form-control'}),
            'tin': forms.TextInput(attrs={'class': 'form-control'}),
            'gsis_id': forms.TextInput(attrs={'class': 'form-control'}),
            'pagibig_id': forms.TextInput(attrs={'class': 'form-control'}),
            'philhealth_id': forms.TextInput(attrs={'class': 'form-control'}),
            'sss_id': forms.TextInput(attrs={'class': 'form-control'}),
            'jo_date_hired': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reg_date_hired': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'assigned_department_memo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }



class CitizenProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CitizenProfile
        fields = ['contact_number', 'address']
        widgets = {
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }
