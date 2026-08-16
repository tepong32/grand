from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
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
