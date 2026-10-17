"""Read-only reconciliation of physical-count Accounting CSV archives."""
import json
import os
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from inventory.models import AssetAccountingImport
from inventory.private_evidence import open_checked_private_file


class Command(BaseCommand):
    help = ('Check physical-count Accounting CSV hashes, round namespaces and unreferenced files. '
            'Never changes records or files; use a stopped/restored copy or maintenance window.')

    def handle(self, *args, **options):
        storage = AssetAccountingImport._meta.get_field('source_file').storage
        try:
            root = Path(storage.location).resolve()
        except (AttributeError, NotImplementedError, OSError, RuntimeError) as error:
            raise CommandError('This check requires readable local private file storage.') from error
        namespace = root/'inventory/reconciliation'
        report = {'checked': 0, 'missing': [], 'changed': [], 'unsafe': [], 'unknown': [],
                  'unretained': [], 'unreferenced': [], 'unreadable': []}
        referenced = set()
        for row in AssetAccountingImport.objects.order_by('pk').iterator():
            name = row.source_file.name or ''
            finding = {'id': row.pk, 'path': name}
            if not row.source_sha256:
                report['unknown'].append(finding)
            if not name:
                # Earlier snapshots can retain the source hash without original
                # bytes. Keep that history; never infer a replacement archive.
                report['unretained'].append(finding)
                continue
            referenced.add(root/name)
            report['checked'] += 1  # Archived references examined, not successes.
            try:
                with open_checked_private_file(row.source_file,
                        namespace=f'inventory/reconciliation/{row.verification_round_id}',
                        sha256=row.source_sha256):
                    pass
            except ValueError:
                report['unsafe'].append(finding)
            except FileNotFoundError:
                report['missing'].append(finding)
            except OSError:
                report['unreadable'].append(finding)
            except ValidationError as error:
                if isinstance(error.__cause__, RuntimeError):  # Symlink loop.
                    report['unsafe'].append(finding)
                elif row.source_sha256:
                    report['changed'].append(finding)

        def relative(path):
            try:
                return Path(path).relative_to(root).as_posix()
            except (ValueError, TypeError):
                return 'inventory/reconciliation'

        def unsafe(path):
            try:
                return path.is_symlink() or path.resolve() != path
            except (OSError, RuntimeError):
                return True

        def unreadable(error):
            report['unreadable'].append({'path': relative(error.filename)})

        if unsafe(namespace):
            report['unsafe'].append({'path': 'inventory/reconciliation'})
        else:
            try:
                if namespace.exists():
                    for directory, dirs, files in os.walk(namespace, followlinks=False, onerror=unreadable):
                        dirs.sort()
                        for name in list(dirs):
                            path = Path(directory)/name
                            if unsafe(path):
                                report['unsafe'].append({'path': relative(path)})
                                dirs.remove(name)
                        for name in sorted(files):
                            path = Path(directory)/name
                            if unsafe(path):
                                report['unsafe'].append({'path': relative(path)})
                            elif path not in referenced:
                                report['unreferenced'].append(relative(path))
            except OSError as error:
                unreadable(error)
        self.stdout.write(json.dumps(report, indent=2))
        if any(value for key, value in report.items() if key != 'checked'):
            raise CommandError('Accounting source evidence requires investigation. No records or files were changed.')
