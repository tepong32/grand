from django.urls import path
from . import views

urlpatterns = [

    path('submit/', views.request_assistance_view, name='submit_request'),
    path('edit/<str:reference_code>/', views.edit_request_view, name='edit_request'),
    path('track/<str:reference_code>/', views.track_request_view, name='track_request'),


]
