from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("statement-mappings/", views.statement_mapping_list, name="statement_mapping_list"),
    path("statement-mappings/new/", views.statement_mapping_create, name="statement_mapping_create"),
    path("statement-mappings/<uuid:public_id>/", views.statement_mapping_detail, name="statement_mapping_detail"),
    path("statement-mappings/<uuid:public_id>/edit/", views.statement_mapping_update, name="statement_mapping_update"),
    path("statement-mappings/<uuid:public_id>/lines/new/", views.statement_line_create, name="statement_line_create"),
    path("statement-mappings/<uuid:public_id>/lines/<int:pk>/edit/", views.statement_line_update, name="statement_line_update"),
    path("statement-mappings/<uuid:public_id>/lines/<int:pk>/delete/", views.statement_line_delete, name="statement_line_delete"),
    path("statement-mappings/<uuid:public_id>/submit/", views.statement_mapping_submit, name="statement_mapping_submit"),
    path("statement-mappings/<uuid:public_id>/<str:action>/", views.statement_mapping_review, name="statement_mapping_review"),
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
