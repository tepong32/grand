from django.urls import path

from . import views

app_name = "budget"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("calls/new/", views.call_create, name="call_create"),
    path("calls/<uuid:public_id>/", views.call_detail, name="call_detail"),
    path("calls/<uuid:public_id>/ceilings/new/", views.ceiling_create, name="ceiling_create"),
    path("calls/<uuid:public_id>/<slug:action>/", views.call_action, name="call_action"),
    path("versions/new/", views.version_create, name="version_create"),
    path("versions/consolidate/", views.consolidate, name="consolidate"),
    path("versions/<uuid:public_id>/", views.version_detail, name="version_detail"),
    path("versions/<uuid:public_id>/lines/new/", views.line_create, name="line_create"),
    path("versions/<uuid:public_id>/resources/new/", views.resource_create, name="resource_create"),
    path("versions/<uuid:public_id>/comments/new/", views.comment_create, name="comment_create"),
    path("versions/<uuid:public_id>/export/", views.version_export, name="version_export"),
    path("versions/<uuid:public_id>/compare/", views.version_compare, name="version_compare"),
    path("versions/<uuid:public_id>/<slug:action>/", views.version_action, name="version_action"),
    path("appropriations/new/", views.authorization_create, name="authorization_create"),
    path("appropriations/<uuid:public_id>/", views.authorization_detail, name="authorization_detail"),
    path("appropriations/<uuid:public_id>/export/", views.authorization_export, name="authorization_export"),
    path("appropriations/<uuid:public_id>/<slug:action>/", views.authorization_action, name="authorization_action"),
    path("allotments/", views.allotment_workspace, name="allotment_workspace"),
    path("allotments/new/", views.allotment_create, name="allotment_create"),
    path("allotments/<uuid:public_id>/", views.allotment_detail, name="allotment_detail"),
    path("allotments/<uuid:public_id>/edit/", views.allotment_edit, name="allotment_edit"),
    path("allotments/<uuid:public_id>/lines/new/", views.allotment_line_create, name="allotment_line_create"),
    path("allotments/<uuid:public_id>/lines/<int:line_id>/edit/", views.allotment_line_edit, name="allotment_line_edit"),
    path("allotments/<uuid:public_id>/lines/<int:line_id>/delete/", views.allotment_line_delete, name="allotment_line_delete"),
    path("allotments/<uuid:public_id>/export/", views.allotment_export, name="allotment_export"),
    path("allotments/<uuid:public_id>/<slug:action>/", views.allotment_action, name="allotment_action"),
    path("obligations/", views.obligation_workspace, name="obligation_workspace"),
    path("obligations/new/", views.obligation_create, name="obligation_create"),
    path("obligations/export/", views.obligation_registry_export, name="obligation_registry_export"),
    path("obligations/<uuid:public_id>/", views.obligation_detail, name="obligation_detail"),
    path("obligations/<uuid:public_id>/edit/", views.obligation_edit, name="obligation_edit"),
    path("obligations/<uuid:public_id>/lines/new/", views.obligation_line_create, name="obligation_line_create"),
    path("obligations/<uuid:public_id>/lines/<int:line_id>/edit/", views.obligation_line_edit, name="obligation_line_edit"),
    path("obligations/<uuid:public_id>/lines/<int:line_id>/delete/", views.obligation_line_delete, name="obligation_line_delete"),
    path("obligations/<uuid:public_id>/<slug:action>/", views.obligation_action, name="obligation_action"),
]
