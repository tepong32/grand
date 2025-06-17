# grand

> Working on yet another Django project — this time, aiming for a real launch.  
> Development in progress. Hosted at: https://github.com/tepong32/grand

---

## 🧩 Apps & Progress Overview

### `users` app

- [x] Automatic profile creation upon user registration (with default values)
- [x] Password reset and change workflows functioning correctly  
  ↪ Uses [Mailtrap](https://mailtrap.io) for email testing.

**Next steps:**  
- [ ] Separate registration flows: internal vs external  
- [ ] Integrate `django-allauth` for external login/signup

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

### `assistance` app *(new)*

- [x] User-facing financial assistance request submission with multi-file upload  
- [x] Anonymous request editing and status tracking via secure reference and edit codes  
- [x] Responsive AdminLTE4 + Bootstrap 5 templates for submit, edit, track, and confirmation pages  
- [x] Per-file remarks and status flags for MSWD review  
- [x] Reference code + edit code authentication for request access  
- [x] Duplicate submission prevention based on period, semester, and email  
- [x] Locked editing for approved/claimed requests  
- [x] Message enhancements with contextual helper links  
- [x] Landing page helper for retrieving lost access links  
- [ ] Email confirmation system (ready, currently disabled in dev)

---

## 🔄 Refactor Notes

As part of long-term scaling goals, the project underwent a major refactor to split responsibilities into well-scoped apps instead of overloading the `users` app.

### ✅ Modularization Breakdown:

- **`profiles` app**  
  Handles personal data such as `ext_name`, `date_hired`, and other employee attributes.  
  Designed for HR logic, export readiness, and future extensibility.

- **`departments` app**  
  Manages department listings, contact persons, and department-specific permissions  
  (e.g., head or officer-in-charge access levels for views).

- **`salaries` app**  
  Introduced to manage salary logic in a clean, testable way.  
  Houses initial `EmployeeSalaryDetails` model and will consolidate benefits/deductions logic later.

- **`home` app**  
  Created for general-purpose, public-facing views like department carousels, downloadable forms, and contact details.  
  Serves as a soft landing for non-authenticated users.

### 🧠 Why this matters:

- Improves **code maintainability** and readability  
- Sets up the groundwork for **Django REST Framework** support per app  
- Enables better **role-based access**, admin controls, and future external user onboarding

---

## 🚀 Roadmap / Future Features

- [ ] Vue frontend integration (likely via DRF)  
- [ ] Admin dashboard for summaries and analytics  
- [ ] External user onboarding with constraints  
- [ ] Full i18n support (English/Filipino switch)  
- [ ] Email reminders and update notifications  
- [ ] Print-ready formats for approvals and physical submission

---

## ⚙️ Development Notes

- Django 4+  
- Email testing via [Mailtrap](https://mailtrap.io)  
- Frontend currently AdminLTE4 + Bootstrap 5  
- Uses `crispy-forms` with `bootstrap4` template pack  
- Cron job setup ready in production config

---

## 🤝 Contributions

Not open to public contributors yet — forks, follows, and suggestions welcome.

---

## 📁 Repository

https://github.com/tepong32/grand
