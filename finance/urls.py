from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("releases/new/", views.release_create, name="release_create"),
    path("releases/<int:pk>/", views.release_detail, name="release_detail"),
    path("releases/<int:pk>/<slug:action>/", views.release_action, name="release_action"),
    path("items/new/", views.item_create, name="item_create"),
    path("variants/new/", views.variant_create, name="variant_create"),
    path("document-rules/new/", views.document_rule_create, name="document_rule_create"),
    path("posting-rules/new/", views.posting_rule_create, name="posting_rule_create"),
    path("posting-rule-lines/new/", views.posting_rule_line_create, name="posting_rule_line_create"),
    path("variants/<int:variant_pk>/posting-starter/", views.posting_rule_starter, name="posting_rule_starter"),
    path(
        "variants/<int:variant_pk>/payment-posting-starters/",
        views.payment_posting_starters,
        name="payment_posting_starters",
    ),
    path("signatories/new/", views.signatory_create, name="signatory_create"),
    path("parties/new/", views.party_create, name="party_create"),
    path("parties/<int:party_pk>/claimants/new/", views.claimant_create, name="claimant_create"),
    path("sequences/new/", views.sequence_create, name="sequence_create"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/starter/", views.starter_template, name="starter_template"),
    path("templates/<int:pk>/preflight/", views.template_preflight, name="template_preflight"),
    path("templates/<int:pk>/download/", views.template_download, name="template_download"),
    path("templates/<int:pk>/synthetic-preview/", views.template_preview, name="template_preview"),
    path("shadow-cutover/", views.shadow_workspace, name="shadow_workspace"),
    path("shadow-cutover/cycles/new/", views.shadow_cycle_create, name="shadow_cycle_create"),
    path("shadow-cutover/cycles/<int:pk>/", views.shadow_cycle_detail, name="shadow_cycle_detail"),
    path("shadow-cutover/cycles/<int:pk>/export/", views.shadow_cycle_export, name="shadow_cycle_export"),
    path("shadow-cutover/cycles/<int:cycle_pk>/sources/upload/", views.shadow_source_upload, name="shadow_source_upload"),
    path("shadow-cutover/cycles/<int:cycle_pk>/sources/external-lock/", views.shadow_external_lock, name="shadow_external_lock"),
    path("shadow-cutover/sources/<int:pk>/drift-review/", views.shadow_source_drift_review, name="shadow_source_drift_review"),
    path("shadow-cutover/cycles/<int:cycle_pk>/comparisons/new/", views.shadow_comparison_create, name="shadow_comparison_create"),
    path("shadow-cutover/cycles/<int:cycle_pk>/stakeholders/new/", views.stakeholder_acceptance_create, name="stakeholder_acceptance_create"),
    path("shadow-cutover/stakeholders/<int:pk>/decision/", views.stakeholder_acceptance_decide, name="stakeholder_acceptance_decide"),
    path("shadow-cutover/cycles/<int:cycle_pk>/decision/new/", views.cutover_decision_create, name="cutover_decision_create"),
    path("shadow-cutover/decisions/<int:pk>/<slug:action>/", views.cutover_decision_action, name="cutover_decision_action"),
    path("shadow-cutover/cycles/<int:pk>/<slug:action>/", views.shadow_cycle_action, name="shadow_cycle_action"),
]
