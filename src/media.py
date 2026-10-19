"""Development media delivery must not bypass the checked application routes.

This is scoped to reviewed confidential namespaces, not a declaration
that every other legacy media upload is public or production storage is qualified.
"""
from pathlib import Path, PureWindowsPath

from django.conf import settings
from django.http import Http404
from django.views.static import serve


def serve_development_media(request, path):
    root = Path(settings.MEDIA_ROOT).resolve()
    relative = Path(path)
    try:
        target = root / relative
        normalized = relative.as_posix().casefold()
        components = normalized.split('/')
        if (not path or relative.is_absolute() or PureWindowsPath(path).is_absolute()
                or "\\" in path or ".." in relative.parts or ":" in path
                or target.resolve() != target):
            raise ValueError
        target.relative_to(root)
        if (normalized.split("/", 1)[0] in {"records", "vouchers", "assistance_docs"}
                or normalized.startswith("reporting/outputs/")
                or (len(components) > 3 and components[0] == 'users' and components[2] == 'memos')):
            raise ValueError
    except (ValueError, RuntimeError, OSError):
        raise Http404 from None
    return serve(request, path, document_root=root)
