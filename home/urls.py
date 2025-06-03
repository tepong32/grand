from django.urls import path
# from django documentation -- check CoreyMS' django tutorial Part 8 / 22:30
from .views import (
    UnauthedHomeView,
    AuthedHomeView,
    department_dashboard_redirect,
    hr_dashboard,
    acctg_dashboard,
    gso_dashboard,
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
    path('redirect/', department_dashboard_redirect, name='home_redirect'),

    # 🏠 Default authed home (for users w/o custom dashboards)
    path('home/', AuthedHomeView.as_view(), name='home'),

    # 🧭 Department Dashboards
    path('home/hr/', hr_dashboard, name='hr_dashboard'),
    path('home/acctg/', acctg_dashboard, name='acctg_dashboard'),
    path('home/gso/', gso_dashboard, name='gso_dashboard'),

    # ❌ Unauthorized
    path('unauthorized/', unauthorized_access_view, name='unauthorized_access'),
]
