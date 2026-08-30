from django.urls import path

from . import cash_views, remittance_views, views

app_name = "vouchers"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("cash-position/", cash_views.workspace, name="cash_workspace"),
    path("cash-position/starter.csv", cash_views.starter, name="cash_starter"),
    path("cash-position/new-policy/", cash_views.policy_create, name="cash_policy_create"),
    path("cash-position/export/", cash_views.export, name="cash_export"),
    path("cash-position/exceptions/open/", cash_views.exception_open, name="cash_exception_open"),
    path("cash-position/exceptions/<uuid:public_id>/resolve/", cash_views.exception_resolve, name="cash_exception_resolve"),
    path("cash-position/<uuid:public_id>/", cash_views.policy_detail, name="cash_policy_detail"),
    path("cash-position/<uuid:public_id>/submit/", cash_views.policy_submit, name="cash_policy_submit"),
    path("cash-position/<uuid:public_id>/decide/", cash_views.policy_decide, name="cash_policy_decide"),
    path("cash-position/<uuid:public_id>/positions/new/", cash_views.position_create, name="cash_position_create"),
    path("cash-position/<uuid:public_id>/positions/<uuid:position_id>/submit/", cash_views.position_submit, name="cash_position_submit"),
    path("cash-position/<uuid:public_id>/positions/<uuid:position_id>/decide/", cash_views.position_decide, name="cash_position_decide"),
    path("cash-position/<uuid:public_id>/export/", cash_views.export, name="cash_policy_export"),
    path("remittances/", remittance_views.workspace, name="remittance_workspace"),
    path("remittances/new/", remittance_views.create, name="remittance_create"),
    path("remittances/<uuid:public_id>/", remittance_views.detail, name="remittance_detail"),
    path("remittances/<uuid:public_id>/allocations/add/", remittance_views.add_allocation, name="remittance_add_allocation"),
    path("remittances/<uuid:public_id>/allocations/<int:pk>/revise/", remittance_views.revise_allocation, name="remittance_revise_allocation"),
    path("remittances/<uuid:public_id>/submit/", remittance_views.submit, name="remittance_submit"),
    path("remittances/<uuid:public_id>/review/", remittance_views.review, name="remittance_review"),
    path("remittances/<uuid:public_id>/release/", remittance_views.release, name="remittance_release"),
    path("remittances/<uuid:public_id>/export/", remittance_views.export, name="remittance_export"),
    path("new/", views.case_create, name="case_create"),
    path("<uuid:public_id>/", views.case_detail, name="case_detail"),
    path("<uuid:public_id>/export/transaction/", views.transaction_export, name="transaction_export"),
    path("<uuid:public_id>/export/payment-register/", views.payment_register_export, name="payment_register_export"),
    path("<uuid:public_id>/outputs/<int:output_pk>/download/", views.output_download, name="output_download"),
    path("<uuid:public_id>/<slug:action>/", views.case_action, name="case_action"),
]
