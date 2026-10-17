from django.urls import path

from . import views
from . import property_movement_views
from . import property_output_views
from . import property_card_views
from . import property_views
from . import receiving_views
from . import receipt_amendment_views
from . import receipt_quantity_views
from . import maintenance_views
from . import employee_custody_views
from . import custody_review
from . import custody_return_views
from . import stock_count_views
from . import requisition_views
from . import supply_return_views
from . import hr_custody_review_views

app_name = "inventory"

urlpatterns = [
    path("property-records/spc-sources/", property_card_views.spc_source_worksheet, name="spc-source-worksheet"),
    path("assets/<int:pk>/prepare-ics/", property_output_views.ics_asset_preparation, name="asset-ics-preparation"),
    path("property-records/prepare-ics/", property_output_views.ics_preparation, name="ics-preparation"),
    path("property-records/prepare-spc/", property_output_views.spc_preparation, name="spc-preparation"),
    path("property-records/prepare-par/", property_output_views.par_preparation, name="par-preparation"),
    path("assets/<int:pk>/property-movements/", property_movement_views.movement_list, name="property-movements"),
    path("assets/<int:pk>/property-movements/new/", property_movement_views.movement_new, name="property-movement-new"),
    path("property-movements/<int:pk>/", property_movement_views.movement_detail, name="property-movement-detail"),
    path("property-movements/<int:pk>/evidence/", property_movement_views.movement_evidence, name="property-movement-evidence"),
    path("assets/<int:pk>/property-records/", property_views.property_records, name="property-records"),
    path("property-records/", property_views.property_register, name="property-register"),
    path("property-records/<int:pk>/", property_views.property_detail, name="property-detail"),
    path("property-records/<int:pk>/evidence/", property_views.property_evidence, name="property-evidence"),
    path("supply-returns/", supply_return_views.return_list, name="supply-return-list"),
    path("stock-issues/<int:pk>/return/", supply_return_views.return_start, name="supply-return-start"),
    path("supply-returns/<int:pk>/", supply_return_views.return_detail, name="supply-return-detail"),
    path("supply-returns/<int:pk>/evidence/", supply_return_views.return_evidence, name="supply-return-evidence"),
    path("requisitions/", requisition_views.request_list, name="requisition-list"),
    path("requisitions/new/", requisition_views.request_create, name="requisition-create"),
    path("requisitions/<int:pk>/", requisition_views.request_detail, name="requisition-detail"),
    path("requisitions/<int:pk>/evidence/", requisition_views.request_evidence, name="requisition-evidence"),
    path("hr-custody-reviews/", hr_custody_review_views.review_list, name="hr-custody-review-list"),
    path("hr-custody-reviews/new/<int:employee_id>/", hr_custody_review_views.review_create, name="hr-custody-review-create"),
    path("hr-custody-reviews/<int:pk>/", hr_custody_review_views.review_detail, name="hr-custody-review-detail"),
    path("hr-custody-reviews/<int:pk>/evidence/", hr_custody_review_views.review_evidence, name="hr-custody-review-evidence"),
    path("receiving/lines/<int:pk>/cost-amendments/", receipt_amendment_views.amendments, name="receipt-amendments"),
    path("receiving/cost-amendments/<int:pk>/", receipt_amendment_views.amendment_detail, name="receipt-amendment-detail"),
    path("receiving/cost-amendments/<int:pk>/evidence/", receipt_amendment_views.amendment_evidence, name="receipt-amendment-evidence"),
    path("receiving/lines/<int:pk>/quantity-corrections/", receipt_quantity_views.corrections, name="receipt-quantity-corrections"),
    path("receiving/quantity-corrections/<int:pk>/", receipt_quantity_views.detail, name="receipt-quantity-detail"),
    path("receiving/quantity-corrections/<int:pk>/evidence/", receipt_quantity_views.evidence, name="receipt-quantity-evidence"),
    path("stock-counts/", stock_count_views.count_list, name="stock-count-list"),
    path("consumables/<int:pk>/count/", stock_count_views.count_start, name="stock-count-start"),
    path("stock-counts/<int:pk>/", stock_count_views.count_detail, name="stock-count-detail"),
    path("stock-counts/evidence/<int:pk>/", stock_count_views.count_evidence, name="stock-count-evidence"),
    path("custody-returns/", custody_return_views.return_list, name="custody-return-list"),
    path("<int:pk>/custody-return/", custody_return_views.return_start, name="custody-return-start"),
    path("custody-returns/<int:pk>/", custody_return_views.return_detail, name="custody-return-detail"),
    path("custody-returns/evidence/<int:pk>/", custody_return_views.return_evidence, name="custody-return-evidence"),
    path("custody/", custody_review.custody_review, name="custody-review"),
    path("<int:pk>/employee-handoff/", employee_custody_views.employee_handoff, name="employee-handoff"),
    path("maintenance/", maintenance_views.maintenance_list, name="maintenance-list"),
    path("<int:pk>/maintenance/new/", maintenance_views.maintenance_open, name="maintenance-open"),
    path("maintenance/<int:pk>/", maintenance_views.maintenance_detail, name="maintenance-detail"),
    path("maintenance/evidence/<int:pk>/", maintenance_views.maintenance_evidence, name="maintenance-evidence"),
    path("receiving/", receiving_views.receipt_list, name="receiving-list"),
    path("receiving/new/", receiving_views.receipt_create, name="receiving-create"),
    path("receiving/line/<int:pk>/follow-up/", receiving_views.receipt_followup, name="receiving-followup"),
    path("receiving/<int:pk>/", receiving_views.receipt_detail, name="receiving-detail"),
    path("receiving/evidence/<int:pk>/", receiving_views.evidence_download, name="receiving-evidence"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.asset_list, name="asset-list"),
    path("add/", views.asset_create, name="asset-create"),
    path("<int:pk>/", views.asset_detail, name="asset-detail"),
    path("<int:pk>/edit/", views.asset_edit, name="asset-edit"),
    path("<int:pk>/retire/", views.asset_retire, name="asset-retire"),
    path("transfers/", views.asset_transfer_list, name="asset-transfer-list"),
    path("<int:pk>/transfer/", views.asset_transfer_create, name="asset-transfer-create"),
    path("transfers/<int:pk>/acknowledge/", views.asset_transfer_acknowledge, name="asset-transfer-acknowledge"),
    path("transfers/<int:pk>/cancel/", views.asset_transfer_cancel, name="asset-transfer-cancel"),
    path("disposals/", views.asset_disposal_list, name="asset-disposal-list"),
    path("<int:pk>/disposal-request/", views.asset_disposal_request, name="asset-disposal-request"),
    path("disposals/<int:pk>/", views.asset_disposal_detail, name="asset-disposal-detail"),
    path("disposal-attachments/<int:pk>/", views.disposal_attachment_download, name="disposal-attachment-download"),
    path("verifications/", views.asset_verification_list, name="asset-verification-list"),
    path("verifications/<int:pk>/", views.asset_verification_detail, name="asset-verification-detail"),
    path("verifications/records/<int:pk>/", views.asset_verification_record, name="asset-verification-record"),
    path("verifications/records/<int:pk>/follow-up/", views.asset_verification_followup, name="asset-verification-followup"),
    path("verifications/<int:pk>/findings/add/", views.asset_verification_finding_add, name="asset-verification-finding-add"),
    path("verifications/findings/<int:pk>/review/", views.asset_verification_finding_review, name="asset-verification-finding-review"),
    path("verifications/<int:pk>/reconcile/", views.asset_verification_reconcile, name="asset-verification-reconcile"),
    path("verifications/accounting-template.csv", views.asset_accounting_template, name="asset-accounting-template"),
    path("verifications/accounting-snapshots/<int:pk>/", views.asset_accounting_source_download, name="asset-accounting-source-download"),
    path("verifications/<int:pk>/reconciliation.csv", views.asset_verification_reconciliation_export, name="asset-verification-reconciliation-export"),
    path("export/assets.csv", views.asset_export, name="asset-export"),
    path("consumables/", views.consumable_list, name="consumable-list"),
    path("consumables/export/movements.csv", views.stock_export, name="stock-export"),
    path("consumables/add/", views.consumable_create, name="consumable-create"),
    path("consumables/<int:pk>/edit/", views.consumable_edit, name="consumable-edit"),
    path("consumables/<int:pk>/", views.consumable_detail, name="consumable-detail"),
    path("consumables/<int:pk>/receive/", views.stock_receive, name="stock-receive"),
    path("consumables/<int:pk>/issue/", views.stock_issue, name="stock-issue"),
    path("consumables/<int:pk>/adjust/", views.stock_adjust, name="stock-adjust"),
]
