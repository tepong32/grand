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

    # Filter logic to show this page only to staff or dept heads
    if request.user.is_staff or departments.filter(deptHead_or_oic=request.user).exists():
        messages.info(request, "You are seeing this page because you are a Staff/Admin or a Dept Head/OIC.")
    else:
        messages.error(request, "Access Denied.")
        return redirect('home')

    # Build department -> user list mapping
    department_users = {
        dept: EmployeeProfile.objects.filter(plantilla__department=dept).select_related('user', 'plantilla')
        for dept in departments
    }
    # TEMP DEBUG TEST — manually populate one department with some profiles
    if departments.exists():
        first_dept = departments.first()
        department_users[first_dept] = EmployeeProfile.objects.all()[:3]

    context_data = {
        'users': User.objects.all().order_by('last_name', 'first_name')[:50],
        'profiles': EmployeeProfile.objects.all(),
        'userCount': User.objects.count(),
        'department_users': department_users,
    }
    from pprint import pprint
    pprint(department_users)
    return render(request, 'users/users_index.html', context_data)

# @login_required
# def usersIndexView(request):
#     profiles = EmployeeProfile.objects.all()
#     departments = Department.objects.order_by("name")
#     department_users = {
#         dept: EmployeeProfile.objects.filter(assigned_department=dept)
#         for dept in departments
#     }

#     if request.user.is_staff or departments.filter(deptHead_or_oic=request.user).exists():
#         messages.info(request, "You are seeing this page because you are a Staff/Admin or a Dept Head/OIC.")
#     else:
#         messages.error(request, "Access Denied.")
#         return redirect('home')

#     context_data = {
#         'users': User.objects.all().order_by('last_name', 'first_name')[:50],
#         'profiles': profiles,
#         'userCount': User.objects.count(),
#         'department_users': department_users,
#     }
#     return render(request, 'users/users_index.html', context_data)



# import csv
# import io
# import openpyxl
# from django.http import HttpResponse, HttpResponseForbidden

# @login_required
# def export_department_users(request, department, format):
#     # Lookup department by slug
#     dept = get_object_or_404(Department, slug=department)

#     # Restriction: Only staff or the dept head/OIC can export
#     if not request.user.is_staff and dept.deptHead_or_oic != request.user:
#         messages.error(request, "You are not authorized to export user data for this department.")
#         return redirect('users_index')  # Update this if your index view name is different

#     # Filter users assigned to this department
#     users = EmployeeProfile.objects.filter(assigned_department=dept)

#     # Handle CSV export
#     if format == "csv":
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = f'attachment; filename="{dept.slug}_users.csv"'

#         writer = csv.writer(response)
#         writer.writerow(['Username', 'Last Name', 'First Name', 'Designation'])

#         for u in users:
#             writer.writerow([
#                 u.user.username,
#                 u.user.last_name or '',
#                 u.user.first_name or '',
#                 u.plantilla or ''
#             ])
#         return response

#     # Handle Excel export
#     elif format == "excel":
#         workbook = openpyxl.Workbook()
#         sheet = workbook.active
#         sheet.title = f"{dept.name} Users"

#         # Add headers
#         headers = ['Username', 'Last Name', 'First Name', 'Designation']
#         sheet.append(headers)

#         for u in users:
#             sheet.append([
#                 u.user.username,
#                 u.user.last_name or '',
#                 u.user.first_name or '',
#                 u.plantilla or ''
#             ])

#         # Save Excel to memory
#         excel_file = io.BytesIO()
#         workbook.save(excel_file)
#         excel_file.seek(0)

#         response = HttpResponse(
#             excel_file.read(),
#             content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#         )
#         response['Content-Disposition'] = f'attachment; filename="{dept.slug}_users.xlsx"'
#         return response

#     # Unknown format
#     else:
#         raise Http404("Invalid export format.")
import csv
from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook


@login_required
def export_department_users(request, department, format):
    # Look up department by slug
    dept = get_object_or_404(Department, slug=department)
    
    # Get users in this department
    profiles = EmployeeProfile.objects.filter(plantilla__department=dept).select_related('user', 'plantilla')

    # Define common filename
    filename = f"{dept.slug}_employees.{format}"

    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Last Name', 'First Name', 'Username', 'Designation'])
        
        for profile in profiles:
            user = profile.user
            writer.writerow([
                user.last_name.title() if user.last_name else '',
                user.first_name.title() if user.first_name else '',
                user.username,
                str(profile.plantilla) if profile.plantilla else '',
            ])

        return response

    elif format == 'excel':
        wb = Workbook()
        ws = wb.active
        ws.title = f"{dept.name[:30]}"

        ws.append(['Last Name', 'First Name', 'Username', 'Designation'])

        for profile in profiles:
            user = profile.user
            ws.append([
                user.last_name.title() if user.last_name else '',
                user.first_name.title() if user.first_name else '',
                user.username,
                str(profile.plantilla) if profile.plantilla else '',
            ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response

    else:
        return HttpResponse("Unsupported format", status=400)






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
