"""Protect evidence from accidentally configured public file serving."""
from pathlib import Path
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def check_private_storage(app_configs, **kwargs):
    value = getattr(settings, "DISPOSAL_PRIVATE_ROOT", "")
    private = Path(value)
    if not value or not private.is_absolute():
        return [Error("GSO private evidence requires an absolute directory.", id="inventory.E001")]
    roots = [settings.MEDIA_ROOT, settings.STATIC_ROOT, *getattr(settings, "STATICFILES_DIRS", [])]
    private = private.resolve()
    for value in roots:
        if isinstance(value, (tuple, list)):
            value = value[1]
        if value and (private == Path(value).resolve() or Path(value).resolve() in private.parents):
            return [Error("GSO private evidence must be outside public media/static directories.", id="inventory.E002")]
    return []
