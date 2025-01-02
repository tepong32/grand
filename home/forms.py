from django import forms
from django.forms import SelectDateWidget
from django.core.exceptions import ValidationError
from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'cover_image', 'announcement_type', 'is_pinned', 'published', 'content',]