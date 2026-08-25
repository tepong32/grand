from django.urls import path

from . import views

app_name = "vouchers"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("new/", views.case_create, name="case_create"),
    path("<uuid:public_id>/", views.case_detail, name="case_detail"),
    path("<uuid:public_id>/outputs/<int:output_pk>/download/", views.output_download, name="output_download"),
    path("<uuid:public_id>/<slug:action>/", views.case_action, name="case_action"),
]
