from django import forms
from .models import User

from django.contrib.auth.forms import UserCreationForm


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
	email = forms.EmailField() # to make sure they will be using a valid email address format

	class Meta:
		model = User 
		fields = ["email", "first_name", "middle_name", "last_name", "ext_name"] # main identifier(username) should not be changeable by the user so, it's not included here


