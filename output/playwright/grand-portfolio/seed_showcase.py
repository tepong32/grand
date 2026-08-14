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
from assistance.services.citizen_service import CitizenProfileService
from departments.models import Department, Plantilla
from home.models import Announcement
from leave_mgt.models import LeaveRequest
from profiles.models import EmployeeProfile
from social_welfare.models import ProgramActivity, SocialWelfareProgram
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
departments["mswd"].deptHead_or_oic = mswd_user
departments["mswd"].save(update_fields=["deptHead_or_oic"])

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
for index, (name, email, phone, status, remarks) in enumerate(
    (
        ("Maria Dela Cruz", "maria@example.com", "09170000001", "submitted", "New online application"),
        ("Joshua Reyes", "joshua@example.com", "09170000002", "pending", "Documents ready for initial review"),
        ("Angela Santos", "angela@example.com", "09170000003", "review", "School record verification in progress"),
        ("Carlo Mendoza", "carlo@example.com", "09170000004", "approved", "Approved for scheduled release"),
        ("Maria Dela Cruz", "maria@example.com", "09170000001", "approved", "Prior assistance completed"),
        ("Maria Dela Cruz", "maria@example.com", "09170000001", "denied", "Previous request retained for service history"),
    ),
    start=1,
):
    citizen = CitizenProfileService.get_or_create_citizen(
        full_name=name,
        email=email,
        phone=phone,
    )
    AssistanceRequest.objects.update_or_create(
        reference_code=f"MSWD-SHOWCASE-{index:03d}",
        defaults={
            "assistance_type": program,
            "period": "2026-2027",
            "semester": "1st",
            "full_name": name,
            "email": email,
            "phone": phone,
            "status": status,
            "remarks": remarks,
            "is_active": True,
            "citizen": citizen,
        },
    )
    CitizenProfileService.increment_request_count(citizen)

nutrition_program, _ = SocialWelfareProgram.objects.update_or_create(
    department=departments["mswd"],
    code="MSWD-NUTRITION-2026",
    defaults={
        "name": "Community Nutrition and Family Wellness",
        "program_type": SocialWelfareProgram.TYPE_FEEDING,
        "description": "Coordinated feeding, nutrition education, and family wellness activities in priority barangays.",
        "status": SocialWelfareProgram.STATUS_ACTIVE,
        "coordinator": mswd_user,
        "start_date": today,
        "end_date": today + timedelta(days=180),
        "created_by": mswd_user,
        "updated_by": mswd_user,
    },
)
family_program, _ = SocialWelfareProgram.objects.update_or_create(
    department=departments["mswd"],
    code="MSWD-FAMILY-2026",
    defaults={
        "name": "Family Development and Protection",
        "program_type": SocialWelfareProgram.TYPE_SEMINAR,
        "description": "Orientations, referral pathways, and community sessions that strengthen family support systems.",
        "status": SocialWelfareProgram.STATUS_ACTIVE,
        "coordinator": mswd_user,
        "start_date": today - timedelta(days=45),
        "end_date": today + timedelta(days=120),
        "created_by": mswd_user,
        "updated_by": mswd_user,
    },
)
for program_record, title, activity_type, start_offset, venue, status, expected, actual, outcome in (
    (
        nutrition_program,
        "Community Feeding and Nutrition Seminar",
        ProgramActivity.TYPE_FEEDING,
        7,
        "Barangay Mabuhay Multi-Purpose Hall",
        ProgramActivity.STATUS_PLANNED,
        120,
        None,
        "",
    ),
    (
        family_program,
        "Parent Effectiveness and Child Protection Orientation",
        ProgramActivity.TYPE_ORIENTATION,
        14,
        "Municipal Training Hall",
        ProgramActivity.STATUS_PLANNED,
        85,
        None,
        "",
    ),
    (
        nutrition_program,
        "Nutrition Screening and Family Referral Day",
        ProgramActivity.TYPE_OUTREACH,
        -21,
        "MSWD Community Center",
        ProgramActivity.STATUS_COMPLETED,
        75,
        68,
        "Families received nutrition screening results and service referral materials.",
    ),
):
    starts_at = timezone.now() + timedelta(days=start_offset)
    ProgramActivity.objects.update_or_create(
        program=program_record,
        title=title,
        defaults={
            "activity_type": activity_type,
            "starts_at": starts_at,
            "ends_at": starts_at + timedelta(hours=3),
            "venue": venue,
            "status": status,
            "expected_attendance": expected,
            "actual_attendance": actual,
            "outcome_notes": outcome,
            "created_by": mswd_user,
            "updated_by": mswd_user,
        },
    )

print("Showcase database seeded.")
print(f"Dashboard users: showcase_hr, showcase_gso, showcase_acctg, showcase_planning, showcase_mswd")
print(f"Password: {SHOWCASE_PASSWORD}")
