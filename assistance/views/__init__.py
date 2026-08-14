from .public import (
    submit_assistance_view,
    confirmation_view,
    edit_request_view,
    track_request_view,
    assistance_landing,
    generate_qr,
    resend_codes_view,
    validate_codes_view,
    delete_document_view,
    upload_document_ajax,
)
from .staff import (
    citizen_profile_detail_view,
    citizen_profile_list_view,
    mswd_dashboard_view,
    mswd_request_detail_view,
    mswd_printable_view,
    mswd_update_document_ajax,
)

submit_request = submit_assistance_view
