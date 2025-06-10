# grand

> Working on yet another Django project — this time, aiming for a real launch.  
> Development in progress. Hosted at: https://github.com/tepong32/grand

---

## Apps & Progress Overview

### users app

- [x] Automatic profile creation upon user registration (with default values)
- [x] Password reset and change workflows functioning correctly  
  ↪ Uses [Mailtrap](https://mailtrap.io) for email testing.

**Next steps:**  
- [ ] Separate registration flows: internal vs external  
- [ ] Integrate `django-allauth` for external login/signup

---

### leave app

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

### announcements app

- [x] Basic structure: public/internal, pinned, draft vs posted  
- [ ] Redesign user-facing views

---

### salary app *(remodel pending)*

- [ ] Logic planning stage — will affect multiple modules

---

### working_days app *(not started)*

- [ ] Needed for holiday detection, leave and salary integration, calendar generation

---

### assistance app *(new)*

- [x] User-facing financial assistance request submission with multi-file upload  
- [x] Anonymous request editing and status tracking via secure reference and edit codes  
- [x] Responsive AdminLTE4 + Bootstrap 5 templates for submit, edit, track, and confirmation pages  
- [x] Confirmation page clearly displays links and instructions for saving access credentials  
- [ ] Email notification currently disabled during development, planned for future integration

---

## Roadmap / Future Features

- [ ] Vue frontend integration (likely via DRF)  
- [ ] Admin dashboard for summaries and analytics  
- [ ] External user onboarding with constraints

---

## Development Notes

- Django 4+  
- Email testing via [Mailtrap](https://mailtrap.io)  
- Frontend currently AdminLTE3, plans to migrate to Vue

---

## Contributions

Not open to public contributors yet — forks, follows, and suggestions welcome.

---

## Repository

https://github.com/tepong32/grand
