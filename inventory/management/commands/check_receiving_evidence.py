"""Read-only evidence reconciliation for maintenance windows and restored copies."""
import hashlib
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from inventory.models import ReceivingEvidence


class Command(BaseCommand):
    help = "Check receiving evidence hashes and report unreferenced files. Never changes data or files."
    evidence_model = ReceivingEvidence
    namespace_name = "receiving"
    report_unknown_hashes = False

    def handle(self, *args, **options):
        storage = self.evidence_model._meta.get_field("file").storage
        if not hasattr(storage, "location"):
            raise CommandError("This check requires the configured local private file storage.")
        root = Path(storage.location).resolve()
        namespace = root / "inventory" / self.namespace_name
        report = {"checked": 0, "missing": [], "changed": [], "unsafe": [], "unreferenced": []}
        if self.report_unknown_hashes:
            report["unknown"] = []
        referenced = set()
        for record in self.evidence_model.objects.order_by("pk").iterator():
            name = record.file.name
            path = root / name
            try:
                path.resolve().relative_to(namespace)
                if ".." in Path(name).parts or path.resolve() != path:
                    raise ValueError
            except ValueError:
                report["unsafe"].append({"id": record.pk, "path": name})
                continue
            referenced.add(path.resolve())
            report["checked"] += 1
            try:
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                        size += len(block)
            except OSError:
                report["missing"].append({"id": record.pk, "path": name})
                continue
            if self.report_unknown_hashes and not record.sha256:
                report["unknown"].append({"id": record.pk, "path": name})
            if (record.sha256 and digest.hexdigest() != record.sha256 or size != record.size
                    or not record.sha256 and not self.report_unknown_hashes):
                report["changed"].append({"id": record.pk, "path": name})

        def unreadable(error):
            raise CommandError(f"Cannot enumerate {self.namespace_name} storage; check filesystem access.") from error

        if namespace.resolve() != namespace:
            report["unsafe"].append({"path": f"inventory/{self.namespace_name}"})
        else:
            for directory, dirs, files in os.walk(namespace, followlinks=False, onerror=unreadable):
                for name in list(dirs):
                    path = Path(directory) / name
                    if path.resolve() != path:
                        report["unsafe"].append({"path": path.relative_to(root).as_posix()})
                        dirs.remove(name)
                for name in files:
                    path = Path(directory) / name
                    relative = path.relative_to(root).as_posix()
                    if path.resolve() != path:
                        report["unsafe"].append({"path": relative})
                    elif path.resolve() not in referenced:
                        report["unreferenced"].append(relative)
        self.stdout.write(json.dumps(report, indent=2))
        if any(report[key] for key in report if key != "checked"):
            raise CommandError(f"{self.namespace_name.title()} evidence requires investigation. No data or files were changed.")
