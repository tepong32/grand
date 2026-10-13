from django import forms
from .models import User

from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from departments.models import Department


'''
	These forms are the ones the users will be using when registering or updating their account info.
	They will be specifically added to their respective views, in our case:
	
	user.views.register > UserRegisterForm
	user.views.profileEditView > UserUpdateForm
'''

class UserRegisterForm(UserCreationForm):
	email = forms.EmailField() # to make sure they will be using a valid email address format

	class Meta:
		model = User
		fields = ["username", "email", "password1", "password2", 'first_name', 'middle_name', 'last_name', 'ext_name', ]


class UserUpdateForm(forms.ModelForm):
	class Meta:
		model = User 
		# Recovery email is a credential. HR profile authority must not confer
		# account takeover through password reset; owners use allauth verification.
		fields = ["first_name", "middle_name", "last_name", "ext_name"]


class EmployeeRegisterForm(UserRegisterForm):
    assigned_department = forms.ModelChoiceField(queryset=Department.objects.order_by("name"), help_text="Select the employee's authorized office. Module permissions are assigned separately.")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = user.employeeprofile
            profile.assigned_department = self.cleaned_data["assigned_department"]
            profile.save(update_fields=["assigned_department"])
        return user


