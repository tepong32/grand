from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from .models import User
from .forms import UserRegisterForm
from django.db.models import Q
import logging
from departments.models import Department
from profiles.models import EmployeeProfile


logger = logging.getLogger(__name__)

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    return render(request, 'auth/register.html', {'form': form})


def employeeRegister(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    return render(request, 'auth/employee_register.html', {'form': form})


def user_search_view(request):
    context = {}
    if request.method == "GET":
        search_query = request.GET.get("q")
        try:
            if search_query and len(search_query) > 0:
                search_results = User.objects.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query)
                ).distinct()
                accounts = [(account, False) for account in search_results]
                context['accounts'] = accounts
                context['search_query'] = search_query
        except Exception as e:
            logger.error(f"Search error: {e}")
    return render(request, "users/user_search_results.html", context)





@login_required
def usersIndexView(request):
    departments = Department.objects.order_by("name")

    # Restrict access to staff or dept heads
    if request.user.is_staff or departments.filter(deptHead_or_oic=request.user).exists():
        messages.info(request, "You are seeing this page because you are a Staff/Admin or a Dept Head/OIC.")
    else:
        messages.error(request, "Access Denied.")
        return redirect('home')

    # View is now based on actual assigned_department (not plantilla)
    department_users = {
        dept: EmployeeProfile.objects.filter(
            assigned_department=dept
        ).select_related('user', 'plantilla')
        for dept in departments
    }

    context_data = {
        'users': User.objects.all().order_by('last_name', 'first_name')[:50],
        'profiles': EmployeeProfile.objects.all(),
        'userCount': User.objects.count(),
        'department_users': department_users,
    }

    return render(request, 'users/users_index.html', context_data)


import csv
from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from collections import defaultdict


@login_required
def export_department_users(request, department, format):
    dept = get_object_or_404(Department, slug=department)

    profiles = EmployeeProfile.objects.filter(
        assigned_department=dept
    ).select_related('user', 'plantilla', 'assigned_department')

    filename = f"{dept.slug}_employees"

    headers = [
        'Last Name', 'First Name', 'Middle Name', 'Username', 'Email',
        'Contact No.', 'Status', 'Assigned Department', 'Plantilla',
        'Position Title', 'Employee Type', 'Date Hired', 'Date of Birth',
        'Address', 'TIN', 'GSIS No.', 'Pag-IBIG No.', 'PhilHealth No.', 'SSS No.'
    ]

    def get_safe(obj, attr):
        value = getattr(obj, attr, '')
        return str(value) if value is not None else ''

    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

        writer = csv.writer(response)
        writer.writerow(headers)

        for profile in profiles:
            user = profile.user
            writer.writerow([
                get_safe(user, 'last_name').title(),
                get_safe(user, 'first_name').title(),
                get_safe(profile, 'middle_name').title(),
                get_safe(user, 'username'),
                get_safe(user, 'email'),
                get_safe(profile, 'contact_number'),
                'Active' if get_safe(user, 'is_active') == 'True' else 'Inactive',
                str(get_safe(profile, 'assigned_department')),
                str(get_safe(profile, 'plantilla')),
                get_safe(profile, 'position_title'),
                get_safe(profile, 'employment_type'),
                get_safe(profile, 'date_hired'),
                get_safe(profile, 'date_of_birth'),
                get_safe(profile, 'address'),
                get_safe(profile, 'tin'),
                get_safe(profile, 'gsis_number'),
                get_safe(profile, 'pagibig_number'),
                get_safe(profile, 'philhealth_number'),
                get_safe(profile, 'sss_number'),
            ])
        return response

    elif format == 'excel':
        wb = Workbook()
        ws = wb.active
        ws.title = dept.name[:30]

        # Write headers with bold font
        bold_font = Font(bold=True)
        ws.append(headers)
        for col_num, _ in enumerate(headers, 1):
            ws.cell(row=1, column=col_num).font = bold_font

        for profile in profiles:
            user = profile.user
            ws.append([
                get_safe(user, 'last_name').title(),
                get_safe(user, 'first_name').title(),
                get_safe(profile, 'middle_name').title(),
                get_safe(user, 'username'),
                get_safe(user, 'email'),
                get_safe(profile, 'contact_number'),
                'Active' if get_safe(user, 'is_active') == 'True' else 'Inactive',
                str(get_safe(profile, 'assigned_department')),
                str(get_safe(profile, 'plantilla')),
                get_safe(profile, 'position_title'),
                get_safe(profile, 'employment_type'),
                get_safe(profile, 'date_hired'),
                get_safe(profile, 'date_of_birth'),
                get_safe(profile, 'address'),
                get_safe(profile, 'tin'),
                get_safe(profile, 'gsis_number'),
                get_safe(profile, 'pagibig_number'),
                get_safe(profile, 'philhealth_number'),
                get_safe(profile, 'sss_number'),
            ])

        # Total at bottom
        total_row = [''] * (len(headers) - 1) + [f'Total: {profiles.count()}']
        ws.append(total_row)

        # Auto-resize columns
        for col in ws.columns:
            max_length = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or '')
                if val:
                    max_length = max(max_length, len(val))
            ws.column_dimensions[col_letter].width = max(max_length + 2, 12)

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response

    else:
        return HttpResponse("Unsupported format", status=400)


@login_required
def export_all_employees(request, format):
    profiles = EmployeeProfile.objects.select_related('user', 'assigned_department', 'plantilla')

    wb = Workbook()
    ws_all = wb.active
    ws_all.title = "All Employees"
    headers = ['Department', 'Last Name', 'First Name', 'Username', 'Email', 'Mobile', 'Designation', 'Remarks']
    ws_all.append(headers)

    dept_map = defaultdict(list)
    for profile in profiles:
        dept = profile.assigned_department.name if profile.assigned_department else 'Unassigned'
        dept_map[dept].append(profile)

    for dept, dept_profiles in dept_map.items():
        for profile in dept_profiles:
            user = profile.user
            ws_all.append([
                dept,
                user.last_name.title() if user.last_name else '',
                user.first_name.title() if user.first_name else '',
                user.username,
                user.email or '',
                getattr(profile, 'mobile', ''),
                str(profile.plantilla) if profile.plantilla else '',
                getattr(profile, 'remarks', '')
            ])

    # Department-specific sheets
    for dept, dept_profiles in dept_map.items():
        ws_dept = wb.create_sheet(title=dept[:30])
        ws_dept.append(headers)
        for profile in dept_profiles:
            user = profile.user
            ws_dept.append([
                dept,
                user.last_name.title() if user.last_name else '',
                user.first_name.title() if user.first_name else '',
                user.username,
                user.email or '',
                getattr(profile, 'mobile', ''),
                str(profile.plantilla) if profile.plantilla else '',
                getattr(profile, 'remarks', '')
            ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="all_employees.xlsx"'
    return response




class CustomPasswordResetView(PasswordResetView):
    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            logger.info("Password reset email sent to: %s", form.cleaned_data['email'])
            return response
        except Exception as e:
            logger.error("Failed to send password reset email to %s: %s", form.cleaned_data['email'], str(e))
            form.add_error(None, _("There was an error sending the password reset email. Please try again later."))
            return self.form_invalid(form)
