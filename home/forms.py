from django import forms

from django_ckeditor_5.widgets import CKEditor5Widget
from django.core.exceptions import ValidationError
from django.forms import SelectDateWidget

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
          super().__init__(*args, **kwargs)
          self.fields["title"].required = False
          self.fields["content"].required = False

    class Meta:
        model = Announcement
        fields = ['title', 'cover_image', 'announcement_type', 'is_pinned', 'published', 'content',]
        widgets = {
              "text": CKEditor5Widget(
                  attrs={"class": "django_ckeditor_5"}, config_name="extends"
              )
          }