from django.urls import path, include
from .views import *


### complete this some other time ###
urlpatterns = [
    path('search/', user_search_view, name='user-search' ), # this should be first as urls catches errors whtn using the search function if it's not
    path('', usersIndexView, name='users-list'),
    path('<username>/', profileView, name='profile' ),
    path('<username>/edit/', profileEditView, name='profile-edit' ),


]
