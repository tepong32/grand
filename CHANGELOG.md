## [Unreleased]







## 2025-06-27
### ✨ Added
- Two-step flow for submitting assistance requests:
  - **Step 1**: Personal and request info
  - **Step 2**: Upload supporting documents via edit link
- AJAX-based document upload with:
  - Document type selection
  - Real-time feedback and previews
  - Status-based restrictions (cannot replace approved files)
- File preview thumbnails for images on the edit page
- UI indicators (dot progress) to guide users through multi-step process

### 🔧 Changed
- Separated document upload form from the initial submission form
- Improved status display and remark visibility for uploaded files
- Updated submission confirmation email with clearer instructions

### 🐛 Fixed
- URL reverse errors for `upload_document_ajax`
- Custom `basename` template filter not loading due to missing templatetag config
- Session corruption warnings on improper form structure
- JS logic now prevents uploads of already approved files


## [2025-06-26] Assistance App
### ✨ Added
- Telegram bot handler (`telegram_bot/bot_handler.py`) with `/start`, `/unlink`, and secure request linking
- Telegram notifications for document updates (in `mswd_update_document_ajax`) if user is linked
- Environment variable support via `.env` for `TELEGRAM_BOT_TOKEN`

### 🔒 Security
- Only requests with `claimed_at=None` can be linked or receive messages
- Reference + Edit code required to link; prevents unauthorized access
- Telegram messages gracefully fail if request no longer exists

### 🧹 Housekeeping
- Telegram bot logs to `telegram_bot.log`
- Inline bot logic included in AJAX view instead of helper for now
- Test data cleanup to be done manually before live deployment


## [2025-06-25] Profiles App – Edit Logs and HR Metadata Expansion

### Added
- `ProfileEditLog` model to track profile edits with section, note, timestamp, and editor metadata.
- HR/admin edit log display in `profile.html` (visible to profile owner or admins only).
- Colored highlight (`bg-light border-left-info`) for HR/admin-initiated changes in logs.
- Full field support in `EmploymentProfileUpdateForm`, including:
  - Government IDs: TIN, GSIS ID, PAG-IBIG ID, PhilHealth ID, SSS ID
  - Dates: `jo_date_hired`, `reg_date_hired`
  - File: `assigned_department_memo` (with preview and file path)

### Changed
- Refactored `profileEditView` to:
  - Detect employee vs. citizen profiles and handle forms accordingly
  - Log edits to `ProfileEditLog` with section labeling (`Basic Info`, `HR Metadata`, etc.)
  - Support admin-only HR metadata updates conditionally
- `profile.html` now uses partials and includes an expandable audit log section
- Edit forms grouped visually with Bootstrap cards and consistent form controls

### Fixed
- Catch-block for missing slug in `get_absolute_url`, resolving `NoReverseMatch` on profile save
- Template fallback for missing logs or null `edited_by` (displayed as “System”)
- Fixed memo preview display when no file is uploaded (file path and click logic included)

### Notes
- Logs currently stored indefinitely; may paginate or archive in future
- Profile page URLs still based on username (internal use); slug fallback maintained
- Minimal performance impact expected due to low log volume


## [2025-06-23] Assistance Dashboard and Transparency Logs

### Added
- MSWD dynamic dashboard with recent assistance request summary and quick access to request details.
- Per-request status change logging via `RequestLog` model (action type, who updated, timestamps).
- Transparency log display for MSWD: “who updated what and when”.
- Email notifications sent to citizens upon status or remarks changes.
- Printable and downloadable request summary for MSWD using `html2pdf.js`.

### Changed
- `mswd_request_detail_view`: now logs updates, sends email, and supports printable view UI.
- Department dashboard routing now smartly loads MSWD dashboard using the `dashboard_template` field.

### Fixed
- Resolved Django template error: inline `if...else` in logs display now uses proper `{% if %}` blocks.


## [2025-06-15] Assistance App
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
