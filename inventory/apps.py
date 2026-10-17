from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"
    verbose_name = "GSO Asset Inventory"

    def ready(self):
        from . import checks
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        if not settings.DEBUG:
            errors = checks.check_private_storage(None)
            if errors:
                raise ImproperlyConfigured(errors[0].msg)
