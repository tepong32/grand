from django.urls import path

from . import views

app_name = "tracepoint"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("new/", views.packet_create, name="packet_create"),
    path("daily-code/", views.daily_code, name="daily_code"),
    path("daily-code/image/", views.daily_code_image, name="daily_code_image"),
    path("daily-code/revoke/", views.daily_code_revoke, name="daily_code_revoke"),
    path("scan/packet/<uuid:public_id>/", views.packet_scan, name="packet_scan"),
    path("scan/session/<uuid:public_id>/", views.scan_session, name="scan_session"),
    path("scan/session/<uuid:public_id>/confirm/", views.scan_confirm, name="scan_confirm"),
    path("scan/employee/<str:token>/", views.employee_scan, name="employee_scan"),
    path("<uuid:public_id>/label/", views.packet_label, name="packet_label"),
    path("<uuid:public_id>/label/qr.png", views.packet_label_qr, name="packet_label_qr"),
    path("<uuid:public_id>/discrepancies/report/", views.discrepancy_report, name="discrepancy_report"),
    path("<uuid:public_id>/discrepancies/<int:discrepancy_id>/resolve/", views.discrepancy_resolve, name="discrepancy_resolve"),
    path("<uuid:public_id>/custody/correct/", views.custody_correct, name="custody_correct"),
    path("<uuid:public_id>/vouchers/add/", views.packet_item_add, name="packet_item_add"),
    path("<uuid:public_id>/vouchers/split/", views.packet_split, name="packet_split"),
    path("<uuid:public_id>/vouchers/rebundle/", views.packet_rebundle, name="packet_rebundle"),
    path("<uuid:public_id>/checkpoints/add/", views.checkpoint_add, name="checkpoint_add"),
    path("<uuid:public_id>/checkpoints/<int:checkpoint_id>/remove/", views.checkpoint_remove, name="checkpoint_remove"),
    path("<uuid:public_id>/checkpoints/<int:checkpoint_id>/skip/", views.checkpoint_skip, name="checkpoint_skip"),
    path("<uuid:public_id>/<str:action>/", views.packet_action, name="packet_action"),
    path("<uuid:public_id>/", views.packet_detail, name="packet_detail"),
]
