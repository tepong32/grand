from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vouchers.roles import FINANCE_ROLE_PERMISSIONS, FINANCE_UAT_VIEWER_GROUP
from departments.services.internal_howto_seed import seed_finance_internal_howtos


class Command(BaseCommand):
    help = "Create the curated GRAND finance roles and optionally grant read-only UAT access."

    def add_arguments(self, parser):
        parser.add_argument(
            "--uat-viewer",
            action="append",
            default=[],
            metavar="USERNAME",
            help="Add an existing employee account to the read-only Finance UAT Viewer group. Repeat as needed.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        groups = {}
        for group_name, permission_names in FINANCE_ROLE_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            permissions = []
            missing = []
            for permission_name in permission_names:
                app_label, codename = permission_name.split(".", 1)
                permission = Permission.objects.filter(
                    content_type__app_label=app_label,
                    codename=codename,
                ).first()
                if permission is None:
                    missing.append(permission_name)
                else:
                    permissions.append(permission)
            if missing:
                raise CommandError(
                    "Run migrations before configuring finance roles. Missing permissions: "
                    + ", ".join(missing)
                )
            group.permissions.set(permissions)
            groups[group_name] = group
            state = "created" if created else "updated"
            self.stdout.write(f"{group_name}: {state} with {len(permissions)} permissions")

        user_model = get_user_model()
        viewer_group = groups[FINANCE_UAT_VIEWER_GROUP]
        for username in options["uat_viewer"]:
            try:
                user = user_model.objects.select_related(
                    "employeeprofile__assigned_department"
                ).get(username=username)
            except user_model.DoesNotExist as exc:
                raise CommandError(f"Unknown employee username: {username}") from exc
            profile = getattr(user, "employeeprofile", None)
            if not profile or not profile.assigned_department_id:
                raise CommandError(
                    f"{username} needs an assigned employee department before finance UAT access can be granted."
                )
            user.groups.add(viewer_group)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{username}: read-only Finance UAT Viewer access granted for "
                    f"{profile.assigned_department.name}"
                )
            )

        guide_counts = seed_finance_internal_howtos()
        self.stdout.write(
            f"Internal How-Tos: {guide_counts['guides_created']} created; "
            f"{guide_counts['guides_retired']} superseded; "
            f"{guide_counts['guides_preserved']} published guide(s) preserved."
        )

