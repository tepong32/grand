from django.urls import path

from . import views

app_name = "records"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("new/", views.record_create, name="record_create"),
    path("reports/<uuid:public_id>/file/", views.file_report, name="file_report"),
    path("<uuid:public_id>/", views.record_detail, name="record_detail"),
    path("<uuid:public_id>/files/add/", views.add_file, name="add_file"),
    path("<uuid:public_id>/files/<int:file_id>/download/", views.download_file, name="download_file"),
    path("<uuid:public_id>/sources/<int:association_id>/download/", views.download_source, name="download_source"),
    path("<uuid:public_id>/retention/", views.update_retention, name="update_retention"),
    path("<uuid:public_id>/<str:action>/", views.transition, name="transition"),
]
