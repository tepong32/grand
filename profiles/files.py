"""Current assignment memo delivery under existing sensitive-profile authority."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404

from src.file_integrity import validate_file_namespace


def memo_response(memo):
    source = None
    try:
        parts = Path(memo.name or '').parts
        if len(parts) < 4 or parts[0] != 'users' or parts[2] != 'memos' or ':' in memo.name:
            raise ValueError('Unsafe memo path.')
        validate_file_namespace(memo, namespace='users')
        source = memo.open('rb')
        content_type = 'application/octet-stream'
        from PIL import Image, UnidentifiedImageError
        try:
            image = Image.open(source)
            image.verify()
            content_type = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif'}.get(image.format, content_type)
        except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
            pass
        source.seek(0)
        response = FileResponse(source, as_attachment=content_type == 'application/octet-stream',
                                filename=Path(memo.name).name, content_type=content_type)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = "default-src 'none'; sandbox"
        response['Referrer-Policy'] = 'no-referrer'
        response['X-GRAND-File-Integrity'] = 'not-recorded'
        return response
    except (OSError, ValueError, RuntimeError, ValidationError, NotImplementedError, AttributeError):
        if source is not None:
            source.close()
        raise Http404('Memo unavailable.') from None
    except Exception:
        if source is not None:
            source.close()
        raise
