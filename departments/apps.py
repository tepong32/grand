from django.apps import AppConfig


class DepartmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'departments'

    def ready(self):
        from django.db.models.signals import post_migrate
        from .signals import seed_internal_howtos_after_migrate

        post_migrate.connect(
            seed_internal_howtos_after_migrate,
            sender=self,
            dispatch_uid="departments.seed_internal_howtos_after_migrate",
        )
