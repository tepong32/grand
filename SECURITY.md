# Security maintenance

Grand treats `requirements.txt` as its deployable Python lock set. Development-only security tooling belongs in `requirements-dev.txt` so scanners do not become production dependencies.

For project setup and feature documentation, start with the [GRAND README](README.md) and [documentation map](docs/README.md).

## Local verification

From the repository root, install both requirement sets and run:

```powershell
.\env\Scripts\python.exe -m pip check
.\env\Scripts\python.exe -m pip_audit -r requirements.txt
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py makemigrations --check --dry-run
.\env\Scripts\python.exe manage.py test
.\env\Scripts\python.exe manage.py test telegram_bot
```

Run reporting-specific tests with `manage.py test reporting`. Generated report files and uploaded reference templates are media, not source assets; production storage must be access-controlled and backed up with its database metadata.

The security workflow repeats these checks for pull requests, pushes to `master`, a weekly schedule, and manual dispatches. Dependabot checks Python dependencies weekly and GitHub Actions monthly.

## Bundled browser assets

Grand keeps a minimal AdminLTE 3.2 runtime bundle in `static/admin-lte`. It intentionally excludes upstream demos, build tools, package manifests, and unused plugins. Asset versions and license sources are recorded in `static/admin-lte/THIRD_PARTY_NOTICES.md`.
