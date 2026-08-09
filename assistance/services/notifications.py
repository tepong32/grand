from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape
from django.utils.html import strip_tags


class AssistanceNotificationService:
    @staticmethod
    def _send_email(*, subject, plain_message, html_message, to_email):
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=getattr(settings, "ASSISTANCE_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
            to=[to_email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=True)

    @classmethod
    def send_submission_codes(cls, *, request_obj, track_link, edit_link):
        subject = "Your Assistance Request Confirmation"
        plain_message = (
            f"Hi {escape(request_obj.full_name)},\n\n"
            "Thank you for submitting your request.\n"
            f"Reference Code: {request_obj.reference_code}\n"
            f"Edit Code: {request_obj.edit_code}\n"
            f"Step 2: Continue upload documents -> {edit_link}\n"
            f"Track request: {track_link}\n"
        )
        html_message = f"""
        <p>Hi <strong>{escape(request_obj.full_name)}</strong>,</p>
        <p>Thank you for submitting your financial assistance request.</p>
        <p><strong>Reference Code:</strong> {request_obj.reference_code}</p>
        <p><strong>Edit Code:</strong> {request_obj.edit_code}</p>
        <p>
            <a href="{edit_link}">Continue to Upload Supporting Documents</a>
        </p>
        <p>
            <a href="{track_link}">Track Request</a>
        </p>
        <p style="font-size:0.9em;color:#888;">This is an automated message.</p>
        """.strip()
        cls._send_email(
            subject=subject,
            plain_message=plain_message,
            html_message=html_message,
            to_email=request_obj.email,
        )

    @classmethod
    def send_resend_codes(cls, *, request_obj, track_link, edit_link):
        subject = (
            f"Your Assistance Request for {request_obj.period}"
            f" {escape(request_obj.get_semester_display()) if request_obj.semester else ''}".strip()
        )
        plain_message = (
            f"Hi {escape(request_obj.full_name)},\n\n"
            f"Reference Code: {request_obj.reference_code}\n"
            f"Edit Code: {request_obj.edit_code}\n\n"
            f"Track request: {track_link}\n"
            f"Edit request: {edit_link}\n"
        )
        html_message = f"""
        <p>Hi <strong>{escape(request_obj.full_name)}</strong>,</p>
        <p>Here are your request details for:</p>
        <ul>
            <li><strong>School Year:</strong> {escape(request_obj.period)}</li>
            {f'<li><strong>Semester:</strong> {escape(request_obj.get_semester_display())}</li>' if request_obj.semester else ''}
        </ul>
        <p>
            <strong>Reference Code:</strong> {request_obj.reference_code}<br>
            <strong>Edit Code:</strong> {request_obj.edit_code}
        </p>
        <p>
            <a href="{track_link}">Track Request</a><br>
            <a href="{edit_link}">Edit Request</a>
        </p>
        <p style="font-size:0.9em;color:#888;">This is an automated message.</p>
        """.strip()
        cls._send_email(
            subject=subject,
            plain_message=strip_tags(html_message),
            html_message=html_message,
            to_email=request_obj.email,
        )

    @classmethod
    def send_status_update_email(cls, *, request_obj):
        subject = f"Update on your Assistance Request ({request_obj.reference_code})"
        plain_message = (
            f"Dear {escape(request_obj.full_name)},\n\n"
            f"Your request status has been updated to {request_obj.get_status_display()}.\n\n"
            f"Remarks: {request_obj.remarks or 'None'}"
        )
        html_message = (
            f"<p>Dear {escape(request_obj.full_name)},</p>"
            f"<p>Your request status has been updated to <strong>{request_obj.get_status_display()}</strong>.</p>"
            f"<p>Remarks: {request_obj.remarks or 'None'}</p>"
        )
        cls._send_email(
            subject=subject,
            plain_message=plain_message,
            html_message=html_message,
            to_email=request_obj.email,
        )
