from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import User, Profile
from django.utils.text import slugify
from django.urls import reverse

from ckeditor_uploader.fields import RichTextUploadingField

### for debugging
import logging
logger = logging.getLogger(__name__)


class Announcement(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	title = models.CharField(max_length=255)
	PUBLIC = 'Public'
	INTERNAL = 'Internal'
	PINNED = 'Pinned'
	choices = [
		(PUBLIC, "Public - for the general masses"),
		(INTERNAL, "Internal - for employees only"),
		(PINNED, "Pinned - will be set to the Pinned section, apart from other announcements"),
	]
	annnouncement_type = models.CharField(
		blank=True,
		null=False,
		max_length=20,
		choices=choices,
		default=PUBLIC,
		verbose_name="Type: ",
		help_text="Select the type of announcement. Public is for everyone, Internal is for employees only, and Pinned will be highlighted separately.",
		)
	content = RichTextUploadingField()
	slug = models.SlugField(default='', blank=True)
	def upload_directory_path(instance, filename):
		# file will be uploaded to MEDIA_ROOT/announcements/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
		return 'announcements/{}/{}'.format(instance.user.username, filename)
	cover_image = models.ImageField(default='defaults/jjv.png', blank=True, upload_to=upload_directory_path)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	published = models.BooleanField(default=True) # set a color-coding on the template for published vs unpublished instances


	def __str__(self):
		return self.title.title()

	def get_absolute_url(self):
		return reverse('announcement-detail', kwargs={'slug': self.slug})

	def save(self, *args, **kwargs):
		if not self.slug: # Only slugify if slug is not already set
			base_slug = slugify(self.title)
			slug = base_slug
			counter = 1
			while Announcement.objects.filter(slug=slug).exists():
				slug = f"{base_slug}-{counter}"
				counter += 1
			self.slug = slug
		super(Announcement, self).save(*args, **kwargs)


