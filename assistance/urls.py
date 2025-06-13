from django.urls import path
from . import views

urlpatterns = [

    path('submit/', views.request_assistance_view, name='submit_request'),

    # these will be shown after the submission of a request. Like samples
    path('track/<str:reference_code>/', views.track_request_view, name='track_request'),

    # these are for a separate visit when the user wants to access their request
    path('access/', views.assistance_request_access_entry, name='assistance_access'),
    path('access/view/<str:edit_code>/', views.assistance_request_access_view, name='assistance_request_access_view'),

    # this is for generating a QR code for the request
    path('generate_qr/<str:reference_code>/<str:edit_code>/', views.generate_qr, name='generate_qr'),




]
