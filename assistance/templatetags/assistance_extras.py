import os
from django import template

register = template.Library()

@register.filter
def basename(value):
    """Returns just the filename from a path."""
    return os.path.basename(value)

@register.filter
def filesize(bytes_size):
    """Converts bytes to a human-readable file size (e.g. KB, MB)."""
    try:
        bytes_size = int(bytes_size)
        for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    except:
        return "n/a"

@register.filter
def file_ext(value):
    """Returns the file extension (e.g. 'pdf', 'jpg')."""
    return os.path.splitext(value)[1][1:].lower()  # removes the dot

@register.filter
def badge_class(status):
    return {
        'pending': 'secondary',
        'approved': 'success',
        'clearer_copy': 'warning',
        'wrong_file': 'danger',
        'incomplete': 'info',
        'missing_stamp': 'primary',
        'expired': 'dark',
    }.get(status, 'secondary')

