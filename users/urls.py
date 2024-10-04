from django.urls import path, include
from .views import *


### complete this some other time ###
urlpatterns = [
    path('search/', user_search_view, name='user-search' ), # this should be first as urls catches errors whtn using the search function if it's not
    path('', usersIndexView, name='users-list'),
    path('<username>/', profileView, name='profile' ),
    path('<username>/edit/', profileEditView, name='profile-edit' ),


]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)