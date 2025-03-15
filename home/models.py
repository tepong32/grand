from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import User, Profile
from django.utils.text import slugify
from django.urls import reverse

from django_ckeditor_5.fields import CKEditor5Field
from PIL import Image

### for debugging
import logging
logger = logging.getLogger(__name__)


class Announcement(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	title = models.CharField(max_length=255, blank=False)
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
	content = CKEditor5Field('Content', config_name='extends')
	slug = models.SlugField(default='', blank=True, unique=True)
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
		# file will be uploaded to MEDIA_ROOT/orgpersonnel/<name>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
		return r'orgpersonnel/{}/{}'.format(instance.name, filename)
	image = models.ImageField(default="defaults/jjvbocaue-otimized.png", blank=True, upload_to=upload_directory_path)
	display_order = models.PositiveIntegerField(help_text="Mayor as 1, VM as 2, etc.", blank=True, null=True)

	def __str__(self):
		return self.name.title()

	def save(self, *args, **kwargs):
		# Check if an image has been uploaded
		if self.image:
			try:
				img = Image.open(self.image.path)  # Open the image of the current instance
				if img.height > 600 or img.width > 600:  # Resize if necessary
					output_size = (600, 600)
					img.thumbnail(output_size)
					img.save(self.image.path)
			except Exception as e:
				# Handle exceptions (e.g., file not found, invalid image)
				print(f"Error processing image: {e}")

		super().save(*args, **kwargs)  # Call the original save method


class DepartmentContact(models.Model):
	name = models.CharField(max_length=255)
	motto = CKEditor5Field('Text', config_name='extends', null=True)
	contact_number = models.CharField(max_length=255) # charfield for now since admin naman ang gagamit nito
	email = models.EmailField(unique=True, blank=True)
	messenger_chat_link = models.CharField(max_length=255, null=True, help_text="Your Page's username or profile url here. Ex: tepong32 ")

	def upload_directory_path(instance, filename):
		# file will be uploaded to MEDIA_ROOT/departmentContacts/<name>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
		return r'departmentContacts/{}/{}'.format(instance.name, filename)
	image = models.ImageField(default="defaults/jjvbocaue-otimized.png",blank=True, upload_to=upload_directory_path)

	def __str__(self):
		return self.name.title()

	def save(self, *args, **kwargs):
		# Check if an image has been uploaded
		if self.image:
			try:
				img = Image.open(self.image.path)  # Open the image of the current instance
				if img.height > 600 or img.width > 600:  # Resize if necessary
					output_size = (600, 600)
					img.thumbnail(output_size)
					img.save(self.image.path)
			except Exception as e:
				# Handle exceptions (e.g., file not found, invalid image)
				print(f"Error processing image: {e}")

		super().save(*args, **kwargs)  # Call the original save method
	 