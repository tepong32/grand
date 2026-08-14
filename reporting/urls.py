from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("definitions/new/", views.definition_create, name="definition_create"),
    path("definitions/<int:pk>/", views.definition_detail, name="definition_detail"),
    path("definitions/<int:pk>/edit/", views.definition_update, name="definition_update"),
    path("definitions/<int:pk>/templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/approve/", views.template_approve, name="template_approve"),
    path("schedules/new/", views.schedule_create, name="schedule_create"),
    path("runs/<uuid:public_id>/", views.run_detail, name="run_detail"),
    path("runs/<uuid:public_id>/download/", views.run_download, name="run_download"),
    path("runs/<uuid:public_id>/<str:action>/", views.run_transition, name="run_transition"),
]
