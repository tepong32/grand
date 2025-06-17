from django.urls import path
from . import views

urlpatterns = [
    path('', views.assistance_landing, name='assistance_landing'),
    path('submit/', views.submit_assistance_view, name='submit_request'),
    path('confirm/<str:reference_code>/<str:edit_code>/', views.confirmation_view, name='confirmation_view'),
    path('edit/<str:edit_code>/', views.edit_request_view, name='edit_request'),
    path('track/<str:reference_code>/', views.track_request_view, name='track_request'),
    path('qr/<str:reference_code>/<str:edit_code>/', views.generate_qr, name='generate_qr'),
    path("assistance/resend_codes/", views.resend_codes_view, name="resend_codes"),

]
