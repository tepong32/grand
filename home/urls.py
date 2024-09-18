from django.urls import path
# from django documentation -- check CoreyMS' django tutorial Part 8 / 22:30
from .views import (
    HomeView,
    ApplyLeaveView,
    LeaveUpdateView,
    LeaveDeleteView,
    IncreaseMaxInstancesView,
    check_reset_date,
    )
# alternatively, you can just use "from . import views".
# however, importing views one-by-one seems to be a better option so you can remember which views you have already worked on.


urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('apply-leave/', ApplyLeaveView.as_view(), name='apply-leave'),
    path('leaves/<int:pk>/update/', LeaveUpdateView.as_view(), name='update-leave'),
    path('leaves/<int:pk>/delete/', LeaveDeleteView.as_view(), name='delete-leave'),
    path('increase_max_instances/', IncreaseMaxInstancesView.as_view(), name='increase_max_instances'),
    path('check_reset_date/', check_reset_date, name='check_reset_date'),




    ### these are part of my previous project and are just here for reference of how to make url paths
    ### don't mind these
    # path('<str:slug>/', PostDetailView.as_view(), name='post-detail'),
    # path('<str:username>/', UserPostFilter.as_view(), name='user-posts'),     # filters applied to posts
    # path('add-category/', CategoryCreateView.as_view(), name='add-category'),
    # path('category/<str:cats>/', CategoryView, name='category'),
    # path('<str:slug>/like/', LikeView, name='like_post'),
    ] 

    # replaced <int:pk> with <str:slug>


from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)