# Grand portfolio screenshots

This folder contains reproducible, portfolio-ready captures of Grand's municipal services UI. The images use synthetic people, requests, and departments created by `seed_showcase.py`; no production or citizen data is included.

## Highlights

- `grand-public-services.png` - public municipal service discovery
- `grand-assistance-portal.png` - account-free assistance submission and tracking
- `grand-hr-dashboard.png` - live HR metrics, workforce modules, and department team context
- `grand-dynamic-department-dashboard.png` - generic fallback proving that newly added departments receive a useful dashboard without a custom template
- `grand-mswd-dashboard.png` - department-centered MSWD workspace with a live Assistance summary and future program modules
- `grand-mswd-operations.png` - operational assistance-request queue for MSWD staff

The machine-readable `manifest.json` is the source of truth for portfolio captions, alt text, ordering, and feature descriptions.

## Reproducing the showcase data

Set `DJANGO_SQLITE_PATH` to a disposable SQLite file, run the seed script, and start Django against that same database. The script prints the synthetic login credentials and request reference used for browser QA.

Do not point the seed script at a production database.
