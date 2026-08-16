from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from departments.models import Department


class TrackedPacket(models.Model):
    DRAFT = "draft"
    ACTIVE = "active"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (ACTIVE, "Active"),
        (DELIVERED, "Delivered"),
        (COMPLETED, "Completed"),
        (ON_HOLD, "On hold"),
        (CANCELLED, "Cancelled"),
    )

    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    CONFIDENTIALITY_CHOICES = (
        (INTERNAL, "Internal"),
        (RESTRICTED, "Restricted"),
        (CONFIDENTIAL, "Confidential / sensitive contents"),
    )
    CONFIDENTIALITY_RANK = {INTERNAL: 0, RESTRICTED: 1, CONFIDENTIAL: 2}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    tracking_number = models.CharField(max_length=40, unique=True, db_index=True)
    title = models.CharField(max_length=220)
    contents_manifest = models.TextField()
    expected_document_count = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    expected_page_count = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    confidentiality = models.CharField(max_length=20, choices=CONFIDENTIALITY_CHOICES, default=INTERNAL)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT, db_index=True)

    origin_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="originated_tracepoint_packets")
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_tracepoint_packets")
    final_destination_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="destination_tracepoint_packets")
    final_destination_employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="destination_tracepoint_packets",
    )
    current_holder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="held_tracepoint_packets",
    )
    current_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_tracepoint_packets",
    )

    department_record = models.ForeignKey(
        "records.DepartmentRecord",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tracepoint_packets",
    )
    report_run = models.ForeignKey(
        "reporting.ReportRun",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tracepoint_packets",
    )

    state_version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="completed_tracepoint_packets",
    )
    held_at = models.DateTimeField(null=True, blank=True)
    hold_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-updated_at", "-pk")
        permissions = (
            ("view_tracepoint_workspace", "Can access the TracePoint workspace"),
            ("prepare_tracked_packets", "Can prepare tracked physical packets"),
            ("print_packet_labels", "Can print TracePoint packet labels"),
            ("complete_tracked_packets", "Can complete delivered TracePoint packets"),
            ("resolve_tracepoint_exceptions", "Can resolve TracePoint discrepancies and corrections"),
            ("revoke_employee_credentials", "Can revoke employee TracePoint credentials"),
            ("view_restricted_tracepoint", "Can view restricted TracePoint packets"),
        )

    def __str__(self):
        return f"{self.tracking_number} - {self.title}"

    def get_absolute_url(self):
        return reverse("tracepoint:packet_detail", kwargs={"public_id": self.public_id})

    @staticmethod
    def _department_for_employee(employee):
        profile = getattr(employee, "employeeprofile", None)
        return getattr(profile, "assigned_department", None)

    def clean(self):
        errors = {}
        preparer_department = self._department_for_employee(self.prepared_by) if self.prepared_by_id else None
        if self.prepared_by_id and preparer_department != self.origin_department:
            errors["prepared_by"] = "The preparer must be an employee of the origin department."

        if self.final_destination_employee_id:
            destination_department = self._department_for_employee(self.final_destination_employee)
            if destination_department != self.final_destination_department:
                errors["final_destination_employee"] = "The named recipient must belong to the final destination department."
            if not self.final_destination_employee.is_active:
                errors["final_destination_employee"] = "The named recipient must have an active account."

        if self.current_holder_id:
            holder_department = self._department_for_employee(self.current_holder)
            if not self.current_holder.is_active or holder_department is None:
                errors["current_holder"] = "The current holder must be an active employee with a department assignment."
            if self.current_department_id and holder_department != self.current_department:
                errors["current_department"] = "The current department must match the holder's employee assignment."
        elif self.current_department_id:
            errors["current_department"] = "A current department cannot be recorded without a current holder."

        if self.status == self.DRAFT and (self.current_holder_id or self.current_department_id or self.activated_at):
            errors["status"] = "Draft packets cannot have active custody."
        if self.status != self.DRAFT and not self.current_holder_id and self.status not in (self.CANCELLED,):
            errors["current_holder"] = "A circulating packet must have a current holder."
        if self.status == self.DELIVERED and not self.delivered_at:
            errors["delivered_at"] = "Delivered packets require their server receipt time."
        if self.status == self.COMPLETED and (not self.completed_at or not self.completed_by_id):
            errors["completed_at"] = "Completed packets require the responsible employee and server completion time."
        if self.status == self.ON_HOLD and (not self.held_at or not self.hold_reason.strip()):
            errors["hold_reason"] = "On-hold packets require a reason and server time."
        if self.status == self.CANCELLED and (not self.cancelled_at or not self.cancellation_reason.strip()):
            errors["cancellation_reason"] = "Cancelled packets require a reason and server time."

        if self.department_record_id:
            record = self.department_record
            if record.department_id != self.origin_department_id:
                errors["department_record"] = "The linked record must belong to the packet's origin department."
            if self.CONFIDENTIALITY_RANK[self.confidentiality] < self.CONFIDENTIALITY_RANK.get(record.confidentiality, 0):
                errors["confidentiality"] = "Packet confidentiality cannot be lower than its linked department record."

        if self.report_run_id:
            run = self.report_run
            if run.definition.department_id != self.origin_department_id:
                errors["report_run"] = "The linked report must belong to the packet's origin department."
            if not run.is_official_output:
                errors["report_run"] = "Only approved, department-validated official report outputs may be linked."

        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous:
                immutable = ("public_id", "tracking_number", "origin_department_id", "prepared_by_id")
                if any(getattr(previous, field) != getattr(self, field) for field in immutable):
                    errors["tracking_number"] = "Packet identity, origin, and preparer are immutable."
                if previous.status != self.DRAFT:
                    draft_fields = (
                        "title", "contents_manifest", "expected_document_count", "expected_page_count",
                        "confidentiality", "final_destination_department_id", "final_destination_employee_id",
                        "department_record_id", "report_run_id",
                    )
                    if any(getattr(previous, field) != getattr(self, field) for field in draft_fields):
                        errors["status"] = "Packet contents, sources, and destination are immutable after activation."

        if errors:
            raise ValidationError(errors)


class PacketEvent(models.Model):
    packet = models.ForeignKey(TrackedPacket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tracepoint_packet_events")
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.packet.tracking_number}: {self.action}"

    @property
    def action_label(self):
        return self.action.replace("_", " ").title()


class DailyEmployeeCredential(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tracepoint_daily_credentials")
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    valid_on = models.DateField(db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issued_tracepoint_credentials")
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="revoked_tracepoint_credentials",
    )
    revocation_reason = models.CharField(max_length=255, blank=True)
    replaced_by = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replaces",
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    use_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-valid_on", "-issued_at")
        constraints = (
            models.UniqueConstraint(
                fields=("employee", "valid_on"),
                condition=Q(revoked_at__isnull=True),
                name="one_active_daily_tracepoint_credential",
            ),
        )

    def __str__(self):
        return f"{self.employee} - {self.valid_on:%Y-%m-%d}"

    @property
    def is_valid(self):
        profile = getattr(self.employee, "employeeprofile", None)
        return bool(
            self.revoked_at is None
            and self.valid_on == timezone.localdate()
            and timezone.now() < self.expires_at
            and self.employee.is_active
            and getattr(profile, "assigned_department_id", None)
        )

    def clean(self):
        errors = {}
        profile = getattr(self.employee, "employeeprofile", None) if self.employee_id else None
        if self.employee_id and (not self.employee.is_active or not getattr(profile, "assigned_department_id", None)):
            errors["employee"] = "Daily credentials require an active employee with a department assignment."
        if self.issued_by_id and not self.issued_by.is_active:
            errors["issued_by"] = "The issuing account must be active."
        if self.expires_at and self.valid_on and timezone.localtime(self.expires_at).date() <= self.valid_on:
            errors["expires_at"] = "A daily credential must expire after its valid business date."
        if self.revoked_at and not self.revoked_by_id:
            errors["revoked_by"] = "A revoked credential must identify who revoked it."
        if self.revoked_at and not self.revocation_reason.strip():
            errors["revocation_reason"] = "A revoked credential requires a reason."
        if self.replaced_by_id:
            if self.replaced_by.employee_id != self.employee_id or self.replaced_by.valid_on != self.valid_on:
                errors["replaced_by"] = "A replacement must belong to the same employee and business date."
            if not self.revoked_at:
                errors["replaced_by"] = "A credential must be revoked before it can be replaced."
        if errors:
            raise ValidationError(errors)


class EmployeeCredentialEvent(models.Model):
    credential = models.ForeignKey(DailyEmployeeCredential, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tracepoint_credential_events")
    action = models.CharField(max_length=32)
    note = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.credential}: {self.action}"


class PacketScanSession(models.Model):
    PENDING = "pending"
    READY = "ready"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = (
        (PENDING, "Waiting for employee code"),
        (READY, "Ready for confirmation"),
        (CONFIRMED, "Confirmed"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    )
    OPEN_STATUSES = (PENDING, READY)

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    packet = models.ForeignKey(TrackedPacket, on_delete=models.PROTECT, related_name="scan_sessions")
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="initiated_tracepoint_scans")
    recipient_credential = models.ForeignKey(
        DailyEmployeeCredential,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scan_sessions",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tracepoint_receipt_scans",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    packet_state_version = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("packet",),
                condition=Q(status__in=("pending", "ready")),
                name="one_open_tracepoint_scan_per_packet",
            ),
        )

    def __str__(self):
        return f"{self.packet.tracking_number}: {self.get_status_display()}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def clean(self):
        errors = {}
        if self.recipient_credential_id and self.recipient_id != self.recipient_credential.employee_id:
            errors["recipient"] = "The proposed recipient must match the scanned employee credential."
        if self.status == self.READY and not self.recipient_credential_id:
            errors["recipient_credential"] = "A ready scan requires a validated employee credential."
        if self.status == self.CONFIRMED and not self.confirmed_at:
            errors["confirmed_at"] = "A confirmed scan requires its server confirmation time."
        if self.expires_at and self.created_at and self.expires_at <= self.created_at:
            errors["expires_at"] = "A scan session must expire after it is created."
        if errors:
            raise ValidationError(errors)


class PacketHandoff(models.Model):
    ACTIVATION = "activation"
    RECEIPT = "receipt"
    TYPE_CHOICES = ((ACTIVATION, "Initial activation"), (RECEIPT, "Custody receipt"))

    packet = models.ForeignKey(TrackedPacket, on_delete=models.PROTECT, related_name="handoffs")
    sequence = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    scan_session = models.OneToOneField(PacketScanSession, on_delete=models.PROTECT, related_name="handoff")
    idempotency_key = models.CharField(max_length=64, unique=True)
    transfer_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    from_holder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tracepoint_handoffs_sent",
    )
    to_holder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tracepoint_handoffs_received")
    from_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tracepoint_handoffs_sent",
    )
    to_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="tracepoint_handoffs_received")
    from_employee_name = models.CharField(max_length=255, blank=True)
    from_position_title = models.CharField(max_length=100, blank=True)
    from_department_name = models.CharField(max_length=100, blank=True)
    to_employee_name = models.CharField(max_length=255)
    to_position_title = models.CharField(max_length=100, blank=True)
    to_department_name = models.CharField(max_length=100)
    status_before = models.CharField(max_length=16)
    status_after = models.CharField(max_length=16)
    receipt_note = models.TextField(blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="confirmed_tracepoint_handoffs")
    confirmed_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("sequence", "pk")
        constraints = (
            models.UniqueConstraint(fields=("packet", "sequence"), name="unique_tracepoint_handoff_sequence"),
        )

    def __str__(self):
        return f"{self.packet.tracking_number} receipt {self.sequence}"

    def clean(self):
        errors = {}
        if self.transfer_type == self.ACTIVATION and self.from_holder_id:
            errors["from_holder"] = "Initial activation cannot have a prior holder."
        if self.transfer_type == self.RECEIPT and not self.from_holder_id:
            errors["from_holder"] = "A custody receipt requires the preceding holder."
        if self.from_holder_id and self.from_holder_id == self.to_holder_id:
            errors["to_holder"] = "A holder cannot hand a packet to themselves."
        if self.scan_session_id and self.scan_session.packet_id != self.packet_id:
            errors["scan_session"] = "The scan session must belong to this packet."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Confirmed custody receipts are immutable. Record a correction event instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Confirmed custody receipts cannot be deleted.")


class PacketDiscrepancy(models.Model):
    MISSING_CONTENTS = "missing_contents"
    WRONG_RECIPIENT = "wrong_recipient"
    DAMAGED = "damaged"
    OTHER = "other"
    CATEGORY_CHOICES = (
        (MISSING_CONTENTS, "Missing contents"),
        (WRONG_RECIPIENT, "Wrong recipient or route"),
        (DAMAGED, "Damaged packet or contents"),
        (OTHER, "Other discrepancy"),
    )
    OPEN = "open"
    RESOLVED = "resolved"
    STATUS_CHOICES = ((OPEN, "Open"), (RESOLVED, "Resolved"))

    packet = models.ForeignKey(TrackedPacket, on_delete=models.PROTECT, related_name="discrepancies")
    related_handoff = models.ForeignKey(
        PacketHandoff,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="discrepancies",
    )
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=OPEN, db_index=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_tracepoint_discrepancies")
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_tracepoint_discrepancies",
    )
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-reported_at", "-pk")

    def __str__(self):
        return f"{self.packet.tracking_number}: {self.get_category_display()}"

    def clean(self):
        errors = {}
        if self.related_handoff_id and self.related_handoff.packet_id != self.packet_id:
            errors["related_handoff"] = "The referenced receipt must belong to this packet."
        if self.status == self.RESOLVED and (not self.resolved_by_id or not self.resolved_at or not self.resolution.strip()):
            errors["resolution"] = "Resolved discrepancies require a decision, resolver, and server time."
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous:
                report_fields = ("packet_id", "related_handoff_id", "category", "description", "reported_by_id", "reported_at")
                if any(getattr(previous, field) != getattr(self, field) for field in report_fields):
                    errors["description"] = "The original discrepancy report is immutable."
                if previous.resolved_at:
                    resolution_fields = ("status", "resolved_by_id", "resolution", "resolved_at")
                    if any(getattr(previous, field) != getattr(self, field) for field in resolution_fields):
                        errors["resolution"] = "A resolved discrepancy is immutable. Add a new correction event if needed."
        if errors:
            raise ValidationError(errors)


class PacketCorrection(models.Model):
    packet = models.ForeignKey(TrackedPacket, on_delete=models.PROTECT, related_name="corrections")
    related_handoff = models.ForeignKey(
        PacketHandoff,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
    )
    prior_holder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tracepoint_corrections_from",
    )
    corrected_holder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tracepoint_corrections_to",
    )
    prior_holder_name = models.CharField(max_length=255, blank=True)
    corrected_holder_name = models.CharField(max_length=255)
    prior_department_name = models.CharField(max_length=100, blank=True)
    corrected_department_name = models.CharField(max_length=100)
    reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tracepoint_corrections_created")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.packet.tracking_number}: custody correction"

    def clean(self):
        if self.related_handoff_id and self.related_handoff.packet_id != self.packet_id:
            raise ValidationError({"related_handoff": "The referenced receipt must belong to this packet."})
        if self.prior_holder_id and self.prior_holder_id == self.corrected_holder_id:
            raise ValidationError({"corrected_holder": "The correction must identify a different holder."})

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Custody correction events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Custody correction events cannot be deleted.")
