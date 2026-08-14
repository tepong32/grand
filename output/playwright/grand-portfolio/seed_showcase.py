"""Seed a disposable Grand database for browser QA and portfolio screenshots."""

from datetime import timedelta
import os
from pathlib import Path
import sys

import django
from django.utils import timezone

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings.dev")
django.setup()

from assistance.models import AssistanceRequest, AssistanceType
from departments.models import Department, Plantilla
from home.models import Announcement
from leave_mgt.models import LeaveRequest
from profiles.models import EmployeeProfile
from users.models import User


SHOWCASE_PASSWORD = "GrandShowcase2026!"


def department(name, slug, description, template):
    value, _ = Department.objects.update_or_create(
        slug=slug,
        defaults={
            "name": name,
            "description": description,
            "email": f"{slug}@bocaue.gov.ph",
            "phone": "(044) 123-4567",
            "dashboard_template": template,
        },
    )
    return value


departments = {
    "hr": department(
        "Human Resource Management Office",
        "hr",
        "People, appointments, employee welfare, and workforce services.",
        "home/authed/dashboards/hr.html",
    ),
    "gso": department(
        "General Services Office",
        "gso",
        "Property, supplies, facilities, and procurement support.",
        "home/authed/dashboards/gso.html",
    ),
    "acctg": department(
        "Municipal Accounting Office",
        "acctg",
        "Disbursements, accounting records, compliance, and financial reporting.",
        "home/authed/dashboards/acctg.html",
    ),
    "mpdo": department(
        "Municipal Planning and Development Office",
        "mpdo",
        "Development planning, programs, projects, and municipal data.",
        "",
    ),
    "mswd": department(
        "Municipal Social Welfare and Development Office",
        "mswd",
        "Citizen assistance, social protection, and community support.",
        "home/authed/dashboards/mswd.html",
    ),
}


def employee(username, first_name, last_name, department_key, position, *, staff=False):
    user, _ = User.objects.update_or_create(
        username=username,
        defaults={
            "email": f"{username}@example.gov",
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
            "is_staff": staff,
        },
    )
    user.set_password(SHOWCASE_PASSWORD)
    user.save()
    profile = user.employeeprofile
    profile.assigned_department = departments[department_key]
    profile.position_title = position
    profile.employment_type = "REG"
    profile.save()
    return user


hr_user = employee("showcase_hr", "Ana", "Reyes", "hr", "HR Management Officer")
gso_user = employee("showcase_gso", "Marco", "Santos", "gso", "Property Officer")
acctg_user = employee("showcase_acctg", "Elena", "Cruz", "acctg", "Municipal Accountant")
planning_user = employee("showcase_planning", "Paolo", "Mendoza", "mpdo", "Planning Officer")
mswd_user = employee("showcase_mswd", "Liza", "Garcia", "mswd", "Social Welfare Officer")

for username, first_name, last_name, department_key, position in (
    ("showcase_hr_2", "Mia", "Villanueva", "hr", "Administrative Assistant"),
    ("showcase_hr_3", "Jose", "Navarro", "hr", "Personnel Records Officer"),
    ("showcase_gso_2", "Nico", "Flores", "gso", "Supply Officer"),
    ("showcase_acctg_2", "Cara", "Ramos", "acctg", "Bookkeeper"),
    ("showcase_planning_2", "Iris", "Torres", "mpdo", "Project Development Officer"),
    ("showcase_mswd_2", "Ramon", "Bautista", "mswd", "Community Affairs Officer"),
    ("showcase_mswd_3", "Nina", "Aquino", "mswd", "Social Welfare Assistant"),
):
    employee(username, first_name, last_name, department_key, position)

for title, item_number, grade in (
    ("HR Management Officer", "HR-001", 22),
    ("Personnel Records Officer", "HR-002", 15),
    ("Administrative Assistant", "HR-003", 8),
    ("HR Assistant", "HR-004", 6),
):
    Plantilla.objects.update_or_create(
        item_number=item_number,
        defaults={"title": title, "salary_grade": grade, "department": departments["hr"]},
    )

for profile in EmployeeProfile.objects.filter(assigned_department=departments["hr"]):
    plantilla = Plantilla.objects.filter(
        department=departments["hr"],
        title=profile.position_title,
    ).first()
    if plantilla and profile.plantilla_id != plantilla.id:
        profile.plantilla = plantilla
        profile.save(update_fields=["plantilla"])

today = timezone.localdate()
next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
LeaveRequest.objects.get_or_create(
    employee=hr_user.employeeprofile.leavecredit,
    leave_type="VL",
    start_date=next_monday,
    end_date=next_monday + timedelta(days=1),
    defaults={"status": "PENDING", "notes": "Family appointment"},
)

Announcement.objects.update_or_create(
    slug="grand-digital-services-week",
    defaults={
        "user": hr_user,
        "title": "Digital Services Week",
        "announcement_type": Announcement.INTERNAL,
        "is_pinned": True,
        "published": True,
        "content": "Department teams will review priority digital-service workflows this week.",
    },
)
Announcement.objects.update_or_create(
    slug="grand-records-reminder",
    defaults={
        "user": hr_user,
        "title": "Employee Records Update Reminder",
        "announcement_type": Announcement.INTERNAL,
        "is_pinned": False,
        "published": True,
        "content": "Please verify contact and employment details before month-end.",
    },
)
Announcement.objects.update_or_create(
    slug="grand-public-assistance-advisory",
    defaults={
        "user": mswd_user,
        "title": "Educational Assistance Applications Open",
        "announcement_type": Announcement.PUBLIC,
        "is_pinned": True,
        "published": True,
        "content": "Residents may submit and track educational-assistance requests online.",
    },
)

program, _ = AssistanceType.objects.update_or_create(
    slug="educational-assistance",
    defaults={
        "name": "Educational Assistance",
        "description": "Support for eligible students and families.",
        "requirements": "Birth certificate, certificate of indigency, and current school ID.",
        "is_active": True,
    },
)
for index, (name, status, remarks) in enumerate(
    (
        ("Maria Dela Cruz", "submitted", "New online application"),
        ("Joshua Reyes", "pending", "Documents ready for initial review"),
        ("Angela Santos", "review", "School record verification in progress"),
        ("Carlo Mendoza", "approved", "Approved for scheduled release"),
    ),
    start=1,
):
    AssistanceRequest.objects.update_or_create(
        reference_code=f"MSWD-SHOWCASE-{index:03d}",
        defaults={
            "assistance_type": program,
            "period": "2026-2027",
            "semester": "1st",
            "full_name": name,
            "email": f"applicant{index}@example.com",
            "phone": f"0917000000{index}",
            "status": status,
            "remarks": remarks,
            "is_active": True,
        },
    )

print("Showcase database seeded.")
print(f"Dashboard users: showcase_hr, showcase_gso, showcase_acctg, showcase_planning, showcase_mswd")
print(f"Password: {SHOWCASE_PASSWORD}")
