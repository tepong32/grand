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
    path("signatories/new/", views.signatory_create, name="signatory_create"),
    path("parties/new/", views.party_create, name="party_create"),
    path("parties/<int:party_pk>/claimants/new/", views.claimant_create, name="claimant_create"),
    path("sequences/new/", views.sequence_create, name="sequence_create"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/preflight/", views.template_preflight, name="template_preflight"),
    path("templates/<int:pk>/download/", views.template_download, name="template_download"),
    path("templates/<int:pk>/synthetic-preview/", views.template_preview, name="template_preview"),
]
