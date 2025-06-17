## [Unreleased]

### Added
- New `assistance` app with full request lifecycle
- Per-file review system (remarks + status flags)
- Duplicate prevention for educational assistance
- Reference/edit code access via landing form
- `/assistance` all-in-one submission/tracking/edit page
- Email resend route (`resend_codes`) – disabled in dev
- Global alert system with link-rich contextual messages
- Helper message block on landing page for returning users

### Changed
- Refactored user-related logic into:
  • `profiles` app (employee data)
  • `departments` app (head access + contacts)
  • `salaries` app (pay computation logic)
  • `home` app (public content)
- Switched to AdminLTE4 + Bootstrap 5 UI consistently
- Improved message display and error alert readability

### Fixed
- Message visibility issues on colored backgrounds

### Notes
- Email backend set to development mode (`console` or `mailtrap`)
- Future steps: enable resend_codes mailer and activate cron jobs for status checks
