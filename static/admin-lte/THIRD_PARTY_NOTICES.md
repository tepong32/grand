# Third-party UI runtime assets

This directory intentionally contains only the browser assets loaded by Grand. The previous copy of the complete AdminLTE source, documentation, demos, build tools, and package lock was removed to reduce the deployed attack surface and dependency-alert noise.

## Included components

- AdminLTE 3.2.0 — MIT — https://github.com/ColorlibHQ/AdminLTE/releases/tag/v3.2.0
- jQuery 3.7.1 — MIT — https://jquery.com/
- Bootstrap 4.6.2 bundle — MIT — https://getbootstrap.com/docs/4.6/
- Font Awesome Free 5.15.4 — Font Awesome Free License — https://fontawesome.com/license/free

AdminLTE's upstream license is preserved in `LICENSE`. The other minified assets retain their upstream license banners where provided.

AdminLTE 3.2 is retained temporarily because Grand's templates use Bootstrap 4 markup. Moving to AdminLTE 4 requires a separate Bootstrap 5 interface migration.
