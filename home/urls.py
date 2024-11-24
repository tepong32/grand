from django.urls import path
# from django documentation -- check CoreyMS' django tutorial Part 8 / 22:30
from .views import (
    HomeView,
    ApplyLeaveView,
    LeaveUpdateView,
    LeaveDeleteView,
    )



urlpatterns = [
    path('', HomeView.as_view(), name='home'),


    ### these are part of my previous project and are just here for reference of how to make url paths
    ### don't mind these
    # path('<str:slug>/', PostDetailView.as_view(), name='post-detail'),
    # path('<str:username>/', UserPostFilter.as_view(), name='user-posts'),     # filters applied to posts
    # path('add-category/', CategoryCreateView.as_view(), name='add-category'),
    # path('category/<str:cats>/', CategoryView, name='category'),
    # path('<str:slug>/like/', LikeView, name='like_post'),
    ] 

    # replaced <int:pk> with <str:slug>
