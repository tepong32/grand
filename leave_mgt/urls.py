from django.urls import path, include
from .views import *

urlpatterns = [
    path('', MyLeaveView.as_view(), name="leave_list"),
    path('create/', LeaveApplicationCreateView.as_view(), name='leave_create'),
    # path('<pk>/detail/', LeaveApplicationDetailView.as_view(), name='leave_detail'), # technically, not needed
    path('<pk>/update/', LeaveApplicationUpdateView.as_view(), name='leave_update'),
    path('<pk>/delete/', LeaveApplicationDeleteView.as_view(), name='leave_delete'),

    ]