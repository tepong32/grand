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
    path("templates/<int:pk>/mapping/", views.template_mapping, name="template_mapping"),
    path("templates/<int:pk>/mapping/preflight/", views.template_preflight, name="template_preflight"),
    path("templates/<int:pk>/mapping/<int:mapping_pk>/delete/", views.template_mapping_delete, name="template_mapping_delete"),
    path("templates/<int:pk>/reference/", views.template_reference_download, name="template_reference_download"),
    path("templates/<int:pk>/validate-fidelity/", views.template_validate_fidelity, name="template_validate_fidelity"),
    path("schedules/new/", views.schedule_create, name="schedule_create"),
    path("runs/<uuid:public_id>/", views.run_detail, name="run_detail"),
    path("runs/<uuid:public_id>/download/", views.run_download, name="run_download"),
    path("runs/<uuid:public_id>/control-evidence/", views.run_control_export, name="run_control_export"),
    path("runs/<uuid:public_id>/reproduction-receipt/", views.run_reproduction_receipt, name="run_reproduction_receipt"),
    path("runs/<uuid:public_id>/print/", views.run_print_preview, name="run_print_preview"),
    path("runs/<uuid:public_id>/<str:action>/", views.run_transition, name="run_transition"),
]
