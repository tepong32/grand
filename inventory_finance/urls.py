from django.urls import path
from . import views
from . import journal_mapping_views
from . import property_link_views

app_name = "inventory_finance"
urlpatterns = [
    path("property-links/", property_link_views.workbench, name="property-links"),
    path("property/<uuid:determination_id>/request/", property_link_views.request_link, name="property-link-request"),
    path("property-links/<uuid:link_id>/", property_link_views.detail, name="property-link-detail"),
    path("property-links/<uuid:link_id>/evidence/", property_link_views.evidence, name="property-link-evidence"),
    path("", views.workbench, name="workbench"),
    path("case/<uuid:case_id>/propose/", views.propose, name="propose"),
    path("<uuid:attribution_id>/", views.detail, name="detail"),
    path("<uuid:attribution_id>/journal-sources/", views.journal_sources, name="journal-sources"),
    path("<uuid:attribution_id>/journal-mappings/", journal_mapping_views.workbench, name="journal-mappings"),
    path("journal-mapping/<uuid:mapping_id>/", journal_mapping_views.detail, name="mapping-detail"),
]
