from __future__ import annotations

from pathlib import Path
import os
from datetime import datetime
import re
from uuid import uuid4


def _sanitize_name(value):
    safe = re.sub(r'[^a-zA-Z0-9\s_-]', '', str(value or 'user'))
    return safe.strip().replace(' ', '_')


def temp_memo_path(instance, filename):
    # Retain the callable used by historical migrations. New uploads use a
    # bounded opaque filename, independent of mutable names and departments.
    return f"users/{instance.user_id}/memos/{uuid4().hex}{Path(filename).suffix.lower()}"


def uploaded_images_directory_path(instance, filename):
    return f"users/{_sanitize_name(instance.user.username)}/uploads/{filename}"


def generate_memo_filename(profile, original_filename):
    ext = Path(original_filename).suffix
    date_str = datetime.now().strftime('%Y%m%d')
    dept_name = profile.assigned_department.name if profile.assigned_department else 'no-dept'
    dept_slug = _sanitize_name(dept_name.replace(' ', '_')).lower()
    return f"memo_{profile.user.username}_{dept_slug}_{date_str}{ext}"


def build_memo_path(profile, filename):
    return f"users/{profile.user.username}/memos/{filename}"


def resize_image(image_field, max_size=(600, 600)):
    if not image_field or not hasattr(image_field, 'path'):
        return

    if os.path.exists(image_field.path):
        from PIL import Image

        img = Image.open(image_field.path)
        if img.height > max_size[1] or img.width > max_size[0]:
            img.thumbnail(max_size)
            img.save(image_field.path)
