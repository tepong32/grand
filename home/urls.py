from django.urls import path
# from django documentation -- check CoreyMS' django tutorial Part 8 / 22:30
from .views import (
    UnauthedHomeView,
    OrgChartView,

    AuthedHomeView,
    AnnouncementList,
    CreateAnnouncement,
    AnnouncementDetail,
    UpdateAnnouncement,
    DeleteAnnouncement,
    announcement_search_view
    )



urlpatterns = [
    path('search', announcement_search_view, name='search'),
    path('', UnauthedHomeView.as_view(), name='unauthedhome'),
    path('orgchart', OrgChartView.as_view(), name='orgchart'),
    path('home', AuthedHomeView.as_view(), name='home'),
    
    path('announcement/create/', CreateAnnouncement.as_view(), name='create-announcement'),
    path('announcement/<str:slug>/', AnnouncementDetail.as_view(), name='announcement-detail'),
    path('announcement/<str:slug>/update/', UpdateAnnouncement.as_view(), name='update-announcement'),
    path('announcements/', AnnouncementList.as_view(), name='announcements'),


    ### these are part of my previous project and are just here for reference of how to make url paths
    ### don't mind these
    # path('<str:slug>/', PostDetailView.as_view(), name='post-detail'),
    # path('<str:username>/', UserPostFilter.as_view(), name='user-posts'),     # filters applied to posts
    # path('add-category/', CategoryCreateView.as_view(), name='add-category'),
    # path('category/<str:cats>/', CategoryView, name='category'),
    # path('<str:slug>/like/', LikeView, name='like_post'),
    ] 

    # replaced <int:pk> with <str:slug>
