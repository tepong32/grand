## 🧩 Apps & Progress Overview

### `users` app
- [x] Automatic profile creation upon user registration (with default values)
- [x] Password reset and change workflows working in both dev and production
  ↪ Uses [Mailtrap](https://mailtrap.io) for dev; live SMTP in production
- [x] Secure registration/login for internal users (admin/employee)
- [x] Integrated `django-allauth` for future external signups (already-running in prod, as well)

**Next steps:**  
- [ ] Finalize role assignment logic for external users upon registration

---

### `profiles` app

- [x] Split from `users` for handling both `EmployeeProfile` and `CitizenProfile` data  
- [x] Auto-generated slug URLs with fallback to username  
- [x] Role-aware profile editing view (separate HR-only and owner-only sections)  
- [x] HR metadata form with support for government IDs, position info, and department memo uploads  
- [x] Editable memo image field with preview and re-saving support  
- [x] Profile edit logging via `ProfileEditLog` model  
  ↪ Tracks editor, section changed, notes, and timestamp  
  ↪ Separate styling for HR/admin edits in view-only logs  
- [x] Inline profile edit history displayed conditionally on `profile.html`

**Next steps:**  
- [ ] Add pagination or load-more for logs  
- [ ] Optionally add reason-for-edit dropdown or tag system

---

### `leave` app
- [x] Permissions handled via template logic  
- [x] Leave request auto-deductions for SL/VL on approval  
- [x] Automatic exclusion of weekends in date range  
- [x] Basic validation (`start_date < end_date`)  
- [x] Global context processor for consistent template variables  
- [x] Cron jobs for monthly leave accrual running as expected

**In progress / Notes:**  
- [ ] Manual holiday configuration (branch: `working-days`)  
- [ ] Consider converting leave credits to 15-minute increments  
- [ ] Policy improvements for leave accumulation

---

### `announcements` app
- [x] Basic structure: public/internal, pinned, draft vs posted  
- [ ] Redesign user-facing views

---

### `salary` app *(remodel pending)*
- [ ] Logic planning stage — will affect multiple modules  
- [ ] Will consolidate all pay-related computations into `EmployeeSalaryDetails`

---

### `working_days` app *(not started)*
- [ ] Needed for holiday detection, leave and salary integration, and calendar generation

---

### `assistance` app *(updated)*
- [x] User-facing financial assistance request submission with multi-file upload  
- [x] Anonymous request editing and status tracking via secure reference and edit codes  
- [x] Responsive AdminLTE4 + Bootstrap 5 templates for submit, edit, track, and confirmation pages  
- [x] Per-file remarks and status flags for MSWD review  
- [x] Reference code + edit code authentication for request access  
- [x] Duplicate submission prevention based on period, semester, and email  
- [x] Locked editing for approved/claimed requests  
- [x] Message enhancements with contextual helper links  
- [x] Landing page helper for retrieving lost access links  
- [x] MSWD dashboard with recent request summary and quick access tools  
- [x] Printable and downloadable request views (citizen + MSWD versions)  
- [x] Transparent per-update logs with timestamp and responsible user  
- [x] Automatic email alerts on status/remarks change (opt-out ready)  
- [x] Email confirmation and notifications active in production
  ↪ Status updates, file remarks, and submission confirmations all trigger alerts
- [x] Removed Telegram bot dependency — all updates now delivered via email for broader accessibility


