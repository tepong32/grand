from django.urls import path
from . import views

app_name = "assistance"

urlpatterns = [
    path('', views.assistance_landing, name='assistance_landing'),
    path('submit/', views.submit_assistance_view, name='submit_request'),
    path('confirm/<str:reference_code>/<str:edit_code>/', views.confirmation_view, name='confirmation_view'),
    path('edit/<str:edit_code>/', views.edit_request_view, name='edit_request'),
    path('track/<str:reference_code>/', views.track_request_view, name='track_request'),
    path('qr/<str:reference_code>/<str:edit_code>/', views.generate_qr, name='generate_qr'),
    path('resend_codes/', views.resend_codes_view, name='resend_codes'),
    path('validate_codes/', views.validate_codes_view, name='validate_codes'),
    path('delete-document/', views.delete_document_view, name='delete_document'),
    path('upload/<str:edit_code>/ajax/', views.upload_document_ajax, name='upload_document_ajax'),


    path('mswd/dashboard/', views.mswd_dashboard_view, name='mswd_dashboard'),
    path('mswd/request/<str:ref_code>/', views.mswd_request_detail_view, name='mswd_request_detail'),
    path('mswd/request/<str:ref_code>/print/', views.mswd_printable_view, name='mswd_request_printable'),
    path('mswd/document/update/<int:doc_id>/', views.mswd_update_document_ajax, name='mswd_update_document_ajax'),


]
