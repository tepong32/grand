from django.urls import path
# from django documentation -- check CoreyMS' django tutorial Part 8 / 22:30
from .views import (
    UnauthedHomeView,
    AuthedHomeView,
    department_dashboard_dynamic,
    AnnouncementList,
    CreateAnnouncement,
    AnnouncementDetail,
    UpdateAnnouncement,
    DeleteAnnouncement,
    OrgChartView,
    unauthorized_access_view,
)



urlpatterns = [
    # 🔓 Public views
    path('', UnauthedHomeView.as_view(), name='unauthedhome'),
    path('orgchart/', OrgChartView.as_view(), name='orgchart'),
    path('search/', AnnouncementList.as_view(), name='search'),

    # 📢 Announcement CRUD
    path('announcement/create/', CreateAnnouncement.as_view(), name='create-announcement'),
    path('announcement/<str:slug>/', AnnouncementDetail.as_view(), name='announcement-detail'),
    path('announcement/<str:slug>/update/', UpdateAnnouncement.as_view(), name='update-announcement'),
    path('announcement/<str:slug>/delete/', DeleteAnnouncement.as_view(), name='delete-announcement'),
    path('announcements/', AnnouncementList.as_view(), name='announcements-list'),

    # 🔐 Post-login redirect logic
    # this is where we handle the dynamic dashboard logic depending on the user's department
    # if the user has no custom dashboard, they will be redirected to the default home view (/home)
    path('dashboard/', department_dashboard_dynamic, name='department_dashboard'),
    path('home/', AuthedHomeView.as_view(), name='home'),

    # ❌ Unauthorized
    # If users try to access a view they are not allowed to thru url manipulation,
    # they will be redirected to this view
    path('unauthorized/', unauthorized_access_view, name='unauthorized_access'),
]
