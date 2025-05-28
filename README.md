# grand 💼🛠️

> Working on yet another "to-be-continued / maybe-not" Django project — this time, we might actually ship it.  
> 🧪 Dev in progress. Hosted at: https://github.com/tepong32/grand

---

## 🧩 Apps & Progress Overview

---

### 👤 `users` app

- [x] Automatic profile creation upon user registration (with default values) ✅
- [x] Password reset + change now working properly 🔐  
  ↪ Uses [Mailtrap](https://mailtrap.io) for testing email delivery.

📝 **Next steps:**
- [ ] Separate user registration flows: `internal` vs `external` 👥
- [ ] Integrate `django-allauth` for external user login/signup 🔄

---

### 📅 `leave` app

- [x] View-level permissions handled via template logic instead of mixins 🔍
- [x] Leave request auto-deducts `number_of_days` from current year's SL/VL credit on approval 📉
- [x] Leave date range auto-calculates excluding weekends 🗓️
- [x] Basic validation: `start_date < end_date` ✅
- [x] Added global context via context processor for consistent template variables 🌐
- [x] Cron jobs for monthly accrual running as expected ⏲️  
  ↪ Just need to verify server-local time sync.

🧠 **WIP or notes:**
- [ ] Add manual config for holidays (branch: `working-days`) 📆
- [ ] Consider converting leave credits to 15-min increments (to deduct lates automatically) ⏳
- [ ] Improve leave accumulation policies  
  ↪ For now, these can be manually set in admin via `SL_Accrual` / `VL_Accrual`.

---

### 📢 `announcements` app

- [x] Basic structure complete: public/internal, pinned, draft vs posted 🧾
- [ ] Needs a slight redesign for user-facing view 🖼️

---

### 💰 `salary` app *(remodel pending)*

- [ ] Logic planning phase  
  ↪ Will impact several other modules, so must design with care 💼

---

### 📆 `working_days` app *(not yet started)*

- [ ] Required for:
  - Automatic detection of non-working holidays 🏖️
  - Integration with leave deductions + salary computation
  - Possibly generating official working calendars per user type 🗃️

---

## 🛣️ Roadmap / Future Features

- [ ] Vue frontend integration (possibly via DRF) 🔄
- [ ] Proper admin dashboard for summaries & analytics 📊
- [ ] External user onboarding + registration with constraints 🔒

---

## 🛠️ Dev Notes

- Codebase: Django 4+  
- Email testing: [Mailtrap](https://mailtrap.io)  
- Frontend: Currently AdminLTE3, planning to move to Vue

---

## 🤝 Contributions

Not open to public contributors just yet — but feel free to fork, follow, or suggest issues.

---

## 📌 Repository

🔗 https://github.com/tepong32/grand

