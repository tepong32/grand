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
]
