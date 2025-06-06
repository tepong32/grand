from django.urls import path
from .views import usersIndexView, employeeRegister, user_search_view

urlpatterns = [
    # path('register/', register, name='register'), # this is moved to root/register/ for it will be used by external users to sign-up only using Google accounts. See src/urls.py
    path('', usersIndexView, name='users-list'),
    path('employee-register/', employeeRegister, name='employee-register'),
    path('search/', user_search_view, name='user-search'),
]
