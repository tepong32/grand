import os
from django.core.exceptions import ValidationError

### not being used at, as this chunk is also included on .views

ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.jpg', '.jpeg', '.png', '.gif', '.xls', '.xlsx', '.csv', '.ppt', '.pptx']
MAX_FILE_SIZE_MB = 5

def validate_file_upload(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file type: {ext}")

    if f.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"File size exceeds {MAX_FILE_SIZE_MB}MB.")
