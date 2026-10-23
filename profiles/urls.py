from django.urls import path
from .views import profileView, profileEditView, department_memo

urlpatterns = [
    # path('', usersIndexView, name='users-list'), # moved to root/users/ for it makes sense to be used by HR personnel to view all users
    path('<username>/', profileView, name='profile'),
    path('<username>/edit/', profileEditView, name='profile-edit'),
    path('<username>/memo/', department_memo, name='profile-department-memo'),
]
