from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import User, Profile
from django.utils.text import slugify
from django.urls import reverse

from ckeditor_uploader.fields import RichTextUploadingField
from PIL import Image

### for debugging
import logging
logger = logging.getLogger(__name__)


class Announcement(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	title = models.CharField(max_length=255)
	PUBLIC = 'Public'
	INTERNAL = 'Internal'
	choices = [
		(PUBLIC, "Public - for the general masses"),
		(INTERNAL, "Internal - for employees only"),
	]
	announcement_type = models.CharField(
		blank=True,
		null=False,
		max_length=20,
		choices=choices,
		default=PUBLIC,
		verbose_name="Type: ",
		help_text="Select the type of announcement. Public is for everyone, Internal is for employees only",
		)
	is_pinned = models.BooleanField(default=False, verbose_name="Pinned", help_text="Indicates if the announcement is pinned.")
	published = models.BooleanField(default=True) # set a color-coding on the template for published vs unpublished instances
	content = RichTextUploadingField()
	slug = models.SlugField(default='', blank=True)
	def upload_directory_path(instance, filename):
		# file will be uploaded to MEDIA_ROOT/announcements/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
		return 'announcements/{}/{}'.format(instance.user.username, filename)
	cover_image = models.ImageField(default='defaults/jjv.png', blank=True, upload_to=upload_directory_path)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	


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


class OrgPersonnel(models.Model):
	name = models.CharField(max_length=255)
	title = models.CharField(max_length=255)
	def upload_directory_path(instance, filename):
		# file will be uploaded to MEDIA_ROOT/announcements/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
		return 'orgpersonnel/{}/{}'.format(instance.name, filename)
	image = models.ImageField(blank=True, upload_to=upload_directory_path)
	display_order = models.PositiveIntegerField(default="defaults/default_user_dp.png", help_text="Mayor as 1, VM as 2, etc.", blank=True, null=True)

	def __str__(self):
		return self.name.title()

	def save(self, *args, **kwargs):        # for resizing/downsizing images
		img = Image.open(self.image.path)   # open the image of the current instance
		if img.height > 600 or img.width > 450: # for sizing-down the images to conserve memory in the server
			output_size = (600, 450)
			img.thumbnail(output_size)
			img.save(self.image.path)


class DepartmentContact(models.Model):
	name = models.CharField(max_length=255)
	contact_number = models.CharField(max_length=255) # charfield for now since admin naman ang gagamit nito
	email = models.EmailField(unique=True, blank=True)

	def upload_directory_path(instance, filename):
		# file will be uploaded to MEDIA_ROOT/announcements/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
		return 'departmentContacts/{}/{}'.format(instance.name, filename)
	image = models.ImageField(default="defaults/default_user_dp.png",blank=True, upload_to=upload_directory_path)

	def __str__(self):
		return self.name.title()

	def save(self, *args, **kwargs):        # for resizing/downsizing images
		img = Image.open(self.image.path)   # open the image of the current instance
		if img.height > 600 or img.width > 450: # for sizing-down the images to conserve memory in the server
			output_size = (600, 450)
			img.thumbnail(output_size)
			img.save(self.image.path)
	 