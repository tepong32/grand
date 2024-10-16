from django.urls import path, include
from .views import *

urlpatterns = [
    path('', MyLeaveView.as_view(), name="leave_list"),
    path('create/', LeaveApplicationCreateView.as_view(), name='leave_create'),
    path('<pk>/update/', LeaveApplicationDetailView.as_view(), name='leave_detail'),
    path('<pk>/update/', LeaveApplicationUpdateView.as_view(), name='leave_update'),
    path('<pk>/delete/', LeaveApplicationDeleteView.as_view(), name='leave_delete'),

    ]