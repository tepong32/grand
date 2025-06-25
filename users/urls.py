from django.urls import path
from .views import usersIndexView, employeeRegister, user_search_view, export_department_users, export_all_employees

urlpatterns = [
    # path('register/', register, name='register'), # this is moved to root/register/ for it will be used by external users to sign-up only using Google accounts. See src/urls.py
    path('', usersIndexView, name='users-list'),
    path('employee-register/', employeeRegister, name='employee-register'),
    path('search/', user_search_view, name='user-search'),
    path('users/export/<slug:department>/<str:format>/', export_department_users, name='export_department_users'),
    path('export/all/<str:format>/', export_all_employees, name='export_all_employees'),


]
