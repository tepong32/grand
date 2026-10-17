from pathlib import Path
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from uuid import uuid4


def disposal_private_storage():
    return FileSystemStorage(location=settings.DISPOSAL_PRIVATE_ROOT, base_url=None)


def custody_review_source_path(instance, filename):
    return f"inventory/custody-reviews/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class EmployeeCustodyReview(models.Model):
    """GSO findings for an explicit HR request, never an employment decision."""
    DRAFT, SUBMITTED, REVIEWED, CANCELLED = "draft", "submitted", "reviewed", "cancelled"
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="gso_custody_reviews")
    employee_label = models.CharField(max_length=240)
    reference = models.CharField(max_length=160)
    request_date = models.DateField()
    request_kind = models.CharField(max_length=16, choices=(("movement", "Movement request"),
        ("exit", "Exit request"), ("other", "Other HR request")))
    file = models.FileField(upload_to=custody_review_source_path, storage=disposal_private_storage, max_length=500)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    findings = models.TextField(blank=True)
    coverage_note = models.TextField(blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, default=DRAFT, choices=tuple(
        (value, value.title()) for value in (DRAFT, SUBMITTED, REVIEWED, CANCELLED)))
    outcome = models.CharField(max_length=24, blank=True, choices=(
        ("outstanding", "Outstanding named custody or pending movement"),
        ("no_current_named_items", "No current named items in this office's reviewed scope")))
    state_version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="gso_custody_reviews_created")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="gso_custody_reviews_submitted", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="gso_custody_reviews_decided", null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    pending_employee = models.GeneratedField(expression=models.Case(
        models.When(status__in=("draft", "submitted"), then=models.F("employee_id")),
        default=models.Value(None)), output_field=models.BigIntegerField(null=True), db_persist=False)

    class Meta:
        ordering = ("-created_at", "-pk")
        default_permissions = ("view",)
        permissions = (("record_employeecustodyreview", "Can record HR-reference custody reviews"),
                       ("review_employeecustodyreview", "Can independently review GSO custody findings"))
        constraints = [models.UniqueConstraint(fields=("department_id", "pending_employee"),
            name="gso_one_open_custody_review"), models.CheckConstraint(
            condition=~models.Q(status="reviewed") | (models.Q(reviewed_by__isnull=False, reviewed_at__isnull=False,
                submitted_by__isnull=False, submitted_at__isnull=False) & ~models.Q(reviewed_by=models.F("submitted_by"))
                & ~models.Q(reviewed_by=models.F("created_by")) & ~models.Q(reviewed_by=models.F("employee"))),
            name="gso_custody_review_independent")]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = ("public_id", "department_id", "department_label", "employee_id", "employee_label",
                "reference", "request_date", "request_kind", "file", "original_filename", "sha256", "size",
                "created_by_id", "created_at")
            if not getattr(self, "_workflow_write", False) or any(
                    getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Retain the HR request and review history; use the review workflow.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain the custody review and its source evidence.")


class EmployeeCustodyReviewEvent(models.Model):
    review = models.ForeignKey(EmployeeCustodyReview, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="gso_custody_review_events")
    action = models.CharField(max_length=20)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        default_permissions = ("view",)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Custody review events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain custody review events.")


def property_determination_path(instance, filename):
    return f"inventory/property-determinations/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class PropertyDetermination(models.Model):
    """Supplied property facts verified as documents, not Accounting approval."""
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    asset = models.ForeignKey("Asset", on_delete=models.PROTECT, related_name="property_determinations")
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors")
    treatment = models.CharField(max_length=20, choices=(("ppe", "PPE (as supplied)"), ("semi_expendable", "Semi-expendable (as supplied)")))
    reference = models.CharField(max_length=160)
    source_date = models.DateField()
    source_authority = models.CharField(max_length=240)
    property_class = models.CharField(max_length=160, blank=True)
    fund_label = models.CharField(max_length=160, blank=True)
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_reference = models.CharField(max_length=180, blank=True)
    receipt_item_number = models.CharField(max_length=100, blank=True)
    useful_life = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))])
    life_unit = models.CharField(max_length=6, blank=True, choices=(("days", "Days"), ("months", "Months"), ("years", "Years")))
    life_basis = models.CharField(max_length=240, blank=True)
    life_start = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=500)
    source_snapshot = models.JSONField()
    file = models.FileField(upload_to=property_determination_path, storage=disposal_private_storage, max_length=500)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, default="pending", choices=tuple((v, v.title()) for v in ("pending", "verified", "rejected", "cancelled")))
    state_version = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_property_recorded")
    recorded_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_property_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    pending_asset = models.GeneratedField(expression=models.Case(models.When(status="pending", then=models.F("asset_id")), default=models.Value(None)), output_field=models.BigIntegerField(null=True), db_persist=False)

    class Meta:
        ordering = ("-recorded_at", "-pk")
        default_permissions = ()
        permissions = (("view_property_determination", "Can view supplied property determinations"),
            ("record_property_determination", "Can record supplied property determinations"),
            ("review_property_determination", "Can independently verify supplied property documents"))
        constraints = [models.CheckConstraint(condition=(
            models.Q(acquisition_date__isnull=True, receipt_item_number="") | ~models.Q(acquisition_reference="")),
            name="gso_property_acquisition_ref"),
            models.UniqueConstraint(fields=("pending_asset",), name="gso_one_pending_property_fact"),
            models.CheckConstraint(condition=models.Q(useful_life__isnull=True) | models.Q(useful_life__gt=0), name="gso_property_positive_life"),
            models.CheckConstraint(condition=~models.Q(status__in=("verified", "rejected")) | (
                models.Q(decided_by__isnull=False, decided_at__isnull=False) & ~models.Q(decided_by=models.F("recorded_by"))), name="gso_property_independent")]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            mutable = {"status", "state_version", "decided_by_id", "decided_at", "decision_note"}
            if not getattr(self, "_workflow_write", False) or any(
                getattr(prior, field.attname) != getattr(self, field.attname)
                for field in self._meta.concrete_fields if not field.generated and field.attname not in mutable
            ):
                raise ValidationError("Retain property evidence; use the review workflow.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain property determinations and their history.")


class PropertyDeterminationEvent(models.Model):
    determination = models.ForeignKey(PropertyDetermination, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_property_events")
    action = models.CharField(max_length=16)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Property events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain property events.")


class Asset(models.Model):
    """One register line for an asset or a homogeneous group of assets."""

    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    TRANSFERRED = "transferred"
    RETIRED = "retired"
    ENTRY_VOID = "entry_void"
    EQUIPMENT = "equipment"
    VEHICLE = "vehicle"
    KIND_CHOICES = ((EQUIPMENT, "Equipment / furniture"), (VEHICLE, "Transport vehicle"))
    CLASS_PENDING = "pending_review"
    CLASS_ICT = "ict_equipment"
    CLASS_OFFICE = "office_equipment"
    CLASS_PRINTING = "printing_equipment"
    CLASS_COMMUNICATIONS = "communications_equipment"
    CLASS_MACHINERY = "other_machinery_equipment"
    CLASS_FURNITURE = "furniture_fixtures"
    CLASS_TRANSPORT = "transportation_equipment"
    CLASS_OTHER = "other_equipment"
    INVENTORY_CLASS_CHOICES = (
        (CLASS_PENDING, "Needs Accounting review"),
        (CLASS_ICT, "ICT equipment"),
        (CLASS_OFFICE, "Office equipment"),
        (CLASS_PRINTING, "Printing equipment"),
        (CLASS_COMMUNICATIONS, "Communications equipment"),
        (CLASS_MACHINERY, "Other machinery and equipment"),
        (CLASS_FURNITURE, "Furniture and fixtures"),
        (CLASS_TRANSPORT, "Transportation equipment"),
        (CLASS_OTHER, "Other equipment"),
    )
    ITEM_TYPE_CHOICES = (
        ("desktop", "Desktop computer"),
        ("laptop", "Laptop computer"),
        ("monitor", "Monitor"),
        ("printer", "Printer"),
        ("photocopier", "Photocopier"),
        ("scanner", "Scanner"),
        ("shredder", "Paper shredder"),
        ("bookbinding_machine", "Bookbinding machine"),
        ("ups", "UPS / backup power unit"),
        ("external_drive", "External storage drive"),
        ("camera", "Camera"),
        ("walkie_talkie", "Walkie-talkie / radio"),
        ("sound_system", "Sound / public-address system"),
        ("projector", "Projector"),
        ("network_equipment", "Network equipment"),
        ("desk", "Desk"),
        ("chair", "Chair"),
        ("table", "Table"),
        ("cabinet", "Cabinet"),
        ("shelving", "Shelf / shelving"),
        ("fixture", "Other furniture or fixture"),
        ("motor_vehicle", "Motor vehicle"),
        ("other", "Other / describe below"),
    )
    FURNITURE_ITEM_TYPES = {"desk", "chair", "table", "cabinet", "shelving", "fixture"}
    STATUS_CHOICES = (
        (ACTIVE, "In service"),
        (MAINTENANCE, "Under maintenance"),
        (TRANSFERRED, "Transferred"),
        (RETIRED, "Retired"),
        (ENTRY_VOID, "Corrected erroneous entry"),
    )

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160, default="General Services")
    asset_name = models.CharField(max_length=180, verbose_name="Asset name")
    asset_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=EQUIPMENT)
    inventory_class = models.CharField(
        max_length=32, choices=INVENTORY_CLASS_CHOICES, default=CLASS_PENDING,
        verbose_name="Inventory class",
    )
    item_type = models.CharField(max_length=32, choices=ITEM_TYPE_CHOICES, default="other")
    category = models.CharField(
        max_length=100, blank=True, verbose_name="Additional item description",
        help_text="Optional legacy category or detail. Use the class and item type fields for consistent reporting.",
    )
    property_tag = models.CharField(max_length=100, blank=True, verbose_name="Property tag / asset number")
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True, verbose_name="Model")
    serial_number = models.CharField(max_length=120, blank=True)
    plate_number = models.CharField(max_length=30, blank=True)
    engine_number = models.CharField(max_length=80, blank=True)
    chassis_number = models.CharField(max_length=80, blank=True)
    registration_due = models.DateField(null=True, blank=True)
    obr_reference = models.CharField(max_length=80, blank=True, verbose_name="OBR / reference number")
    purchase_order_reference = models.CharField(max_length=100, blank=True, verbose_name="PO / contract reference")
    voucher_reference = models.CharField(max_length=100, blank=True, verbose_name="Voucher reference")
    journal_reference = models.CharField(max_length=100, blank=True, verbose_name="Journal reference")
    fund_code = models.CharField(max_length=40, blank=True)
    coa_account_code = models.CharField(max_length=40, blank=True, verbose_name="COA account code")
    coa_account_title = models.CharField(max_length=140, blank=True, verbose_name="COA account title")
    coa_basis = models.CharField(max_length=200, blank=True, verbose_name="Reviewed account mapping reference")
    purchase_date = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=160, blank=True)
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    assigned_department_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    assigned_department_label = models.CharField(max_length=160, blank=True)
    assigned_office = models.CharField(max_length=160, blank=True, verbose_name="Assigned office / custodian")
    custodian_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="gso_custodied_assets")
    custodian_snapshot = models.JSONField(default=dict, blank=True)
    last_custody_return = models.ForeignKey("AssetTransfer", on_delete=models.PROTECT,
        null=True, blank=True, related_name="assets_last_returned")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    returned_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_assets_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_assets_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("asset_name", "pk")
        permissions = (
            ("view_asset_audit", "Can view GSO asset change history"),
            ("export_asset_register", "Can export the scoped GSO asset register"),
            ("transfer_asset", "Can initiate GSO asset handoffs"),
            ("record_asset_return", "Can record witnessed asset returns to GSO"),
            ("verify_asset_return", "Can independently confirm witnessed asset returns"),
            ("acknowledge_asset_transfer", "Can acknowledge asset handoffs to the assigned department"),
            ("request_asset_disposal", "Can request assessment for disposal of an assigned asset"),
            ("review_asset_disposal", "Can review and record GSO asset disposal cases"),
            ("start_asset_verification", "Can start GSO physical asset verification rounds"),
            ("record_asset_verification", "Can record physical asset verification results"),
            ("close_asset_verification", "Can close completed physical asset verification rounds"),
            ("import_asset_accounting_snapshot", "Can import an Accounting asset snapshot for reconciliation"),
        )
        indexes = (
            models.Index(fields=("department_id", "status"), name="gso_asset_dept_status"),
            models.Index(fields=("department_id", "asset_name"), name="gso_asset_dept_name"),
        )

    def __str__(self):
        return f"{self.asset_name} ({self.obr_reference or 'No reference'})"


class AssetAuditEvent(models.Model):
    CREATED = "created"
    UPDATED = "updated"
    RETIRED = "retired"
    TRANSFERRED = "transferred"
    DISPOSED = "disposed"
    RETURNED = "returned"
    ACTION_CHOICES = (
        (CREATED, "Created"), (UPDATED, "Updated"), (TRANSFERRED, "Transferred"),
        (RETIRED, "Retired"), (DISPOSED, "Disposed"), (RETURNED, "Returned to GSO"),
    )

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="audit_events")
    department_id = models.PositiveBigIntegerField(db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_audit_events",
    )
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("-occurred_at", "-pk")

    def __str__(self):
        return f"{self.get_action_display()} · asset {self.asset_id} · {self.occurred_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Asset audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Asset audit events are retained and cannot be deleted.")


class AssetTransfer(models.Model):
    HANDOFF = "handoff"
    RETURN = "return"
    """A simple, acknowledged custody handoff for one registered asset."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (PENDING, "Waiting for acknowledgment"),
        (ACCEPTED, "Acknowledged"),
        (CANCELLED, "Cancelled"),
    )

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=12, default=HANDOFF, choices=((HANDOFF, "Handoff"), (RETURN, "Witnessed return")))
    state_version = models.PositiveIntegerField(default=1)
    return_condition = models.CharField(max_length=16, blank=True,
        choices=(("serviceable", "Serviceable"), ("damaged", "Damaged / needs attention"), ("unknown", "Not assessed")))
    return_review_note = models.CharField(max_length=240, blank=True)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="transfers")
    source_custodian_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="gso_custody_handoffs_from")
    source_employee_snapshot = models.JSONField(default=dict, blank=True)
    destination_custodian_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="gso_custody_handoffs_to")
    destination_employee_snapshot = models.JSONField(default=dict, blank=True)
    destination_employee_checksum = models.CharField(max_length=64, blank=True)
    source_department_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_department_label = models.CharField(max_length=160, blank=True)
    source_custodian = models.CharField(max_length=160, blank=True)
    destination_department_id = models.PositiveBigIntegerField(db_index=True)
    destination_department_label = models.CharField(max_length=160)
    destination_custodian = models.CharField(max_length=160)
    transfer_date = models.DateField()
    reason = models.CharField(max_length=240)
    reference = models.CharField(max_length=120, blank=True, verbose_name="PAR / ICS / other reference")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="gso_asset_transfers_requested",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="gso_asset_transfers_acknowledged",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="gso_asset_transfers_cancelled",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=240, blank=True)
    pending_identity_marker = models.GeneratedField(
        expression=models.Case(models.When(status="pending", then=models.Value(1)), default=models.Value(None)),
        output_field=models.PositiveSmallIntegerField(), db_persist=False, null=True,
    )

    class Meta:
        ordering = ("-requested_at", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("asset", "pending_identity_marker"),
                name="gso_one_pending_asset_transfer",
            ),
            models.CheckConstraint(condition=(
                models.Q(kind="handoff", return_condition="")
                | (models.Q(kind="return", source_custodian_user__isnull=False, destination_custodian_user__isnull=True)
                   & models.Q(return_condition__in=("serviceable", "damaged", "unknown")))),
                name="gso_custody_movement_kind"),
        )

    def __str__(self):
        return f"{self.asset.asset_name}: {self.source_department_label or 'Unassigned'} to {self.destination_department_label}"


class AssetVerificationRound(models.Model):
    """A dated GSO exercise that snapshots the assets to be physically checked."""

    title = models.CharField(max_length=160)
    as_of_date = models.DateField(default=timezone.localdate, verbose_name="Physical count as of")
    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_verification_rounds_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_verification_rounds_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    @property
    def is_closed(self):
        return self.closed_at is not None

    def __str__(self):
        return self.title


class AssetVerificationRecord(models.Model):
    NOT_CHECKED = "not_checked"
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"
    NOT_FOUND = "not_found"
    RESULT_CHOICES = (
        (NOT_CHECKED, "Not checked"),
        (MATCHED, "Found and matched"),
        (DISCREPANCY, "Found with a discrepancy"),
        (NOT_FOUND, "Not found during visit"),
    )
    CONDITION_CHOICES = (("serviceable", "Serviceable"), ("damaged", "Damaged / needs attention"), ("unknown", "Not assessed"))
    FOLLOW_UP_OPEN = "open"
    FOLLOW_UP_RESOLVED = "resolved"
    FOLLOW_UP_ACCEPTED = "accepted_difference"
    FOLLOW_UP_CHOICES = (
        (FOLLOW_UP_OPEN, "Follow-up needed"),
        (FOLLOW_UP_RESOLVED, "Resolved"),
        (FOLLOW_UP_ACCEPTED, "Difference reviewed / accepted"),
    )

    verification_round = models.ForeignKey(AssetVerificationRound, on_delete=models.PROTECT, related_name="records")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="verification_records")
    asset_name_snapshot = models.CharField(max_length=180)
    property_tag_snapshot = models.CharField(max_length=100, blank=True)
    serial_number_snapshot = models.CharField(max_length=120, blank=True)
    assigned_department_snapshot = models.CharField(max_length=160, blank=True)
    assigned_office_snapshot = models.CharField(max_length=160, blank=True)
    account_code_snapshot = models.CharField(max_length=40, blank=True)
    account_title_snapshot = models.CharField(max_length=140, blank=True)
    purchase_date_snapshot = models.DateField(null=True, blank=True)
    acquisition_cost_snapshot = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default=NOT_CHECKED, db_index=True)
    observed_department = models.CharField(max_length=160, blank=True)
    observed_office = models.CharField(max_length=160, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    follow_up_status = models.CharField(max_length=24, choices=FOLLOW_UP_CHOICES, default=FOLLOW_UP_OPEN, db_index=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_verification_followups_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_verifications_recorded",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("result", "asset_name_snapshot", "pk")
        constraints = (models.UniqueConstraint(fields=("verification_round", "asset"), name="gso_asset_once_per_verification"),)

    def __str__(self):
        return f"{self.asset_name_snapshot} — {self.get_result_display()}"

    @property
    def needs_followup(self):
        return self.result in (self.DISCREPANCY, self.NOT_FOUND) and self.follow_up_status == self.FOLLOW_UP_OPEN


class AssetVerificationEvent(models.Model):
    record = models.ForeignKey(AssetVerificationRecord, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_verification_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Verification history is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification history is retained and cannot be deleted.")


class AssetVerificationFinding(models.Model):
    """An asset found during a count that was not in that round's register snapshot."""

    PENDING = "pending"
    REGISTERED = "registered"
    NOT_LGU_ASSET = "not_lgu_asset"
    DUPLICATE = "duplicate"
    STATUS_CHOICES = (
        (PENDING, "Needs review"),
        (REGISTERED, "Added to register"),
        (NOT_LGU_ASSET, "Confirmed not an LGU asset"),
        (DUPLICATE, "Duplicate of another record"),
    )

    verification_round = models.ForeignKey(AssetVerificationRound, on_delete=models.PROTECT, related_name="findings")
    asset_name = models.CharField(max_length=180)
    property_tag = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    found_department = models.CharField(max_length=160, blank=True)
    found_office = models.CharField(max_length=160, blank=True)
    condition = models.CharField(max_length=20, choices=AssetVerificationRecord.CONDITION_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    resolution_note = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_findings_recorded",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_findings_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    related_asset = models.ForeignKey(
        Asset, null=True, blank=True, on_delete=models.PROTECT,
        related_name="verification_findings_linked",
    )

    class Meta:
        ordering = ("status", "asset_name", "pk")


def accounting_import_path(instance, filename):
    return f"inventory/reconciliation/{instance.verification_round_id}/{uuid4().hex}.csv"


class AssetAccountingImport(models.Model):
    """Immutable imported snapshot from Accounting for a physical count comparison."""

    verification_round = models.ForeignKey(AssetVerificationRound, on_delete=models.PROTECT, related_name="accounting_imports")
    source_filename = models.CharField(max_length=255)
    source_file = models.FileField(blank=True, default="", upload_to=accounting_import_path, storage=disposal_private_storage)
    source_sha256 = models.CharField(max_length=64)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_accounting_snapshots_imported",
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    line_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-imported_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Accounting snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Accounting snapshots are retained and cannot be deleted.")


class AssetAccountingLine(models.Model):
    accounting_import = models.ForeignKey(AssetAccountingImport, on_delete=models.PROTECT, related_name="lines")
    row_number = models.PositiveIntegerField()
    property_tag = models.CharField(max_length=100, blank=True)
    asset_name = models.CharField(max_length=180)
    serial_number = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=160, blank=True)
    account_code = models.CharField(max_length=40, blank=True)
    account_title = models.CharField(max_length=140, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    acquisition_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("row_number", "pk")
        constraints = (models.UniqueConstraint(fields=("accounting_import", "row_number"), name="gso_accounting_import_row_once"),)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Imported Accounting rows are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Imported Accounting rows are retained and cannot be deleted.")


class AssetVerificationFindingEvent(models.Model):
    finding = models.ForeignKey(AssetVerificationFinding, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_finding_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Verification finding history is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification finding history is retained and cannot be deleted.")


class AssetDisposalCase(models.Model):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_INFORMATION = "needs_information"
    AUTHORIZED = "authorized"
    DISPOSED = "disposed"
    REJECTED = "rejected"
    STATUS_CHOICES = (
        (SUBMITTED, "Submitted to GSO"),
        (UNDER_REVIEW, "Under GSO review"),
        (NEEDS_INFORMATION, "More information needed"),
        (AUTHORIZED, "Authorized for disposal"),
        (DISPOSED, "Disposal completed"),
        (REJECTED, "Request rejected"),
    )
    DISPOSAL_METHOD_CHOICES = (
        ("", "Select after authorization"),
        ("sale", "Sale"),
        ("donation", "Donation"),
        ("transfer", "Transfer"),
        ("barter", "Barter"),
        ("destruction", "Condemnation / destruction"),
    )

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="disposal_cases")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True)
    reason = models.CharField(max_length=240)
    condition_details = models.TextField()
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_disposal_requests",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_disposal_cases_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    authority_reference = models.CharField(max_length=160, blank=True)
    disposal_method = models.CharField(max_length=20, choices=DISPOSAL_METHOD_CHOICES, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    completion_reference = models.CharField(max_length=160, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_disposals_completed",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    open_identity_marker = models.GeneratedField(
        expression=models.Case(models.When(
            status__in=("submitted", "under_review", "needs_information", "authorized"),
            then=models.Value(1)), default=models.Value(None)),
        output_field=models.PositiveSmallIntegerField(), db_persist=False, null=True,
    )

    class Meta:
        ordering = ("-submitted_at", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("asset", "open_identity_marker"),
                name="gso_one_open_disposal_case",
            ),
        )

    def __str__(self):
        return f"Disposal request for {self.asset.asset_name} ({self.get_status_display()})"


def disposal_attachment_path(instance, filename):
    tag = slugify(instance.disposal_case.asset.property_tag or f"asset-{instance.disposal_case.asset_id}")[:70]
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"inventory/disposal/{instance.disposal_case.asset_id}/{tag}-case-{instance.disposal_case_id}-{instance.kind}-{uuid4().hex[:10]}.{extension}"


class AssetDisposalAttachment(models.Model):
    PHOTO = "photo"
    REQUEST_FORM = "request_form"
    SUPPORTING = "supporting"
    KIND_CHOICES = (
        (PHOTO, "Asset condition photo"),
        (REQUEST_FORM, "Signed disposal request form"),
        (SUPPORTING, "Supporting document"),
        ("authority", "Approval / authority document"),
        ("completion", "Disposal completion evidence"),
    )

    disposal_case = models.ForeignKey(AssetDisposalCase, on_delete=models.PROTECT, related_name="attachments")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    file = models.FileField(upload_to=disposal_attachment_path, storage=disposal_private_storage)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_disposal_attachments_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("kind", "uploaded_at", "pk")

    def __str__(self):
        return f"{self.get_kind_display()} for case {self.disposal_case_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Disposal evidence is retained and cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Disposal evidence is retained and cannot be deleted.")


class AssetDisposalEvent(models.Model):
    ACTION_CHOICES = (
        ("submitted", "Submitted"), ("under_review", "Under review"),
        ("needs_information", "More information requested"),
        ("authorized", "Authorized for disposal"), ("disposed", "Disposal completed"),
        ("rejected", "Rejected"), ("resubmitted", "Resubmitted"),
    )
    disposal_case = models.ForeignKey(AssetDisposalCase, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_asset_disposal_events",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Disposal case history is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Disposal case history is retained and cannot be deleted.")


class ConsumableItem(models.Model):
    """A supply item. FIFO is an optional stock allocation aid, not an accounting workflow."""

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160, default="General Services")
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=40, default="piece", help_text="Examples: ream, bottle, box, roll.")
    use_fifo = models.BooleanField(
        default=False,
        verbose_name="Track receipt lots using FIFO",
        help_text="When enabled, issues use the oldest received stock first. Otherwise, track quantities only.",
    )
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_consumables_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_consumables_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "name"), name="gso_unique_consumable_name"),
        )
        permissions = (
            ("receive_stock", "Can record GSO supply receipts"),
            ("issue_stock", "Can issue GSO supplies to departments"),
            ("adjust_stock", "Can adjust GSO supply balances"),
            ("view_stock_audit", "Can view GSO supply movement history"),
            ("export_stock_register", "Can export GSO supply movement history"),
        )

    def __str__(self):
        return f"{self.name} ({self.unit})"

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            if self.movements.exists() and (prior.name != self.name or prior.unit != self.unit):
                raise ValidationError("The name and unit cannot change after stock movements exist.")
            if prior.use_fifo != self.use_fifo and self.movements.exists():
                raise ValidationError({"use_fifo": "FIFO tracking cannot be changed after stock movements exist."})
        return super().save(*args, **kwargs)

    @property
    def on_hand(self):
        from django.db.models import Sum

        total = self.movements.aggregate(total=Sum("signed_quantity"))["total"]
        return total or 0


class ConsumableAuditEvent(models.Model):
    CREATED = "created"
    UPDATED = "updated"
    ACTION_CHOICES = ((CREATED, "Created"), (UPDATED, "Updated"))

    item = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_consumable_audit_events",
    )
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("-occurred_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Supply item audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Supply item audit events are retained and cannot be deleted.")


class StockMovement(models.Model):
    RECEIPT = "receipt"
    ISSUE = "issue"
    RETURN = "return"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    KIND_CHOICES = (
        (RECEIPT, "Received"), (ISSUE, "Issued"), (RETURN, "Returned"),
        (ADJUSTMENT_IN, "Adjustment increase"), (ADJUSTMENT_OUT, "Adjustment decrease"),
    )

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    item = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    signed_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    department_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    department_label = models.CharField(max_length=160, blank=True)
    recipient = models.CharField(max_length=160, blank=True)
    reference = models.CharField(max_length=120, blank=True, help_text="Delivery, requisition, or other reference.")
    reason = models.CharField(max_length=240, blank=True)
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="gso_stock_movements",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-pk")
        indexes = (models.Index(fields=("item", "occurred_at"), name="gso_stock_item_date"),)

    def __str__(self):
        return f"{self.get_kind_display()} · {self.quantity} {self.item.unit} · {self.item.name}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Movement quantity must be greater than zero."})
        inbound = self.kind in (self.RECEIPT, self.RETURN, self.ADJUSTMENT_IN)
        expected = self.quantity if inbound else -self.quantity
        if self.signed_quantity != expected:
            raise ValidationError({"signed_quantity": "The signed quantity must match the movement type."})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Stock movements are immutable. Record a correction as an adjustment.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movements are retained and cannot be deleted.")


class StockLot(models.Model):
    item = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, related_name="lots")
    receipt = models.OneToOneField(StockMovement, on_delete=models.PROTECT, related_name="created_lot")
    received_at = models.DateTimeField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("received_at", "pk")

    def __str__(self):
        return f"{self.item.name} · {self.quantity} {self.item.unit}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("FIFO lots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("FIFO lots are retained and cannot be deleted.")


class StockLotAllocation(models.Model):
    issue = models.ForeignKey(StockMovement, on_delete=models.PROTECT, related_name="lot_allocations")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="allocations")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = (models.UniqueConstraint(fields=("issue", "lot"), name="gso_unique_issue_lot"),)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("FIFO allocations are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("FIFO allocations are retained and cannot be deleted.")


class ReceivingReceipt(models.Model):
    """Physical delivery and inspection evidence; never a Finance approval."""

    DRAFT, SUBMITTED, ACCEPTED, RETURNED = "draft", "submitted", "accepted", "returned"
    STATUS_CHOICES = ((DRAFT, "Draft"), (SUBMITTED, "For review"),
                      (ACCEPTED, "Accepted into inventory"), (RETURNED, "Returned for correction"))
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    followup_source = models.ForeignKey("ReceivingLine", on_delete=models.PROTECT,
        null=True, blank=True, related_name="followup_receipts")
    followup_basis = models.JSONField(default=dict, blank=True)
    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160)
    supplier = models.CharField(max_length=160)
    delivery_reference = models.CharField(max_length=180)
    delivery_date = models.DateField()
    purchase_order_reference = models.CharField(max_length=100, blank=True)
    inspection_reference = models.CharField(max_length=180)
    inspection_date = models.DateField()
    inspector_label = models.CharField(max_length=160)
    evidence_reference = models.TextField(help_text="Location/reference of the retained delivery and inspection documents.")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    state_version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_receipts_created")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_receipts_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        permissions = (("submit_receivingreceipt", "Can submit GSO receiving records"),
                       ("review_receivingreceipt", "Can independently review GSO receiving records"))

    def clean(self):
        if self.delivery_date and self.delivery_date > timezone.localdate():
            raise ValidationError({"delivery_date": "Delivery cannot be in the future."})
        if self.inspection_date and (self.inspection_date > timezone.localdate() or
                                    self.delivery_date and self.inspection_date < self.delivery_date):
            raise ValidationError({"inspection_date": "Inspection must be on or after delivery and not in the future."})


class ReceivingLine(models.Model):
    ASSET, SUPPLY = "asset", "supply"
    receipt = models.ForeignKey(ReceivingReceipt, on_delete=models.PROTECT, related_name="lines")
    sequence = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=12, choices=((ASSET, "Individually tracked asset"), (SUPPLY, "Consumable supply")))
    description = models.CharField(max_length=180)
    unit = models.CharField(max_length=40)
    delivered_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    accepted_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    rejected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    rejection_reason = models.CharField(max_length=240, blank=True)
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    supply_item = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, null=True, blank=True, related_name="receiving_lines")
    asset_kind = models.CharField(max_length=20, choices=Asset.KIND_CHOICES, default=Asset.EQUIPMENT)
    property_tag = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    chassis_number = models.CharField(max_length=80, blank=True)
    is_void = models.BooleanField(default=False)
    registered_asset = models.OneToOneField(Asset, on_delete=models.PROTECT, null=True, blank=True, related_name="receiving_line")
    stock_movement = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="receiving_line")

    class Meta:
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(fields=("receipt", "sequence"), name="gso_receipt_line_sequence"),
            models.CheckConstraint(condition=models.Q(delivered_quantity__gt=0, accepted_quantity__gte=0, rejected_quantity__gte=0), name="gso_receipt_nonnegative_qty"),
            models.CheckConstraint(condition=models.Q(delivered_quantity__gte=models.F("accepted_quantity") + models.F("rejected_quantity")), name="gso_receipt_quantity_capacity"),
        ]

    def clean(self):
        if self.accepted_quantity is not None and self.rejected_quantity is not None and self.delivered_quantity is not None:
            if self.accepted_quantity + self.rejected_quantity > self.delivered_quantity:
                raise ValidationError("Accepted and rejected quantities exceed the delivery.")
        if self.rejected_quantity and not self.rejection_reason.strip():
            raise ValidationError({"rejection_reason": "Explain the rejected quantity."})
        if self.unit_cost is not None and self.unit_cost < 0:
            raise ValidationError({"unit_cost": "Cost cannot be negative."})
        if self.kind == self.ASSET:
            if self.delivered_quantity != 1 or self.accepted_quantity not in (0, 1) or self.rejected_quantity not in (0, 1):
                raise ValidationError("Use one line per individually tracked asset.")
            if self.accepted_quantity and not self.property_tag.strip():
                raise ValidationError({"property_tag": "Record the property tag before accepting this asset."})
            if self.supply_item_id:
                raise ValidationError("An asset line cannot select a supply item.")
        elif self.kind == self.SUPPLY:
            if not self.supply_item_id:
                raise ValidationError({"supply_item": "Select an existing supply item."})
            if self.property_tag or self.serial_number or self.chassis_number:
                raise ValidationError("Use an individually tracked asset line for tagged or serialized property.")
            if self.supply_item_id and (self.supply_item.department_id != self.receipt.department_id or
                                       self.unit != self.supply_item.unit or not self.supply_item.is_active):
                raise ValidationError("Select an active supply in this office and use its registered unit.")


class ReceivingEvent(models.Model):
    receipt = models.ForeignKey(ReceivingReceipt, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_receiving_events")
    action = models.CharField(max_length=32)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Receiving history cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Receiving history is retained.")


def receiving_evidence_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"inventory/receiving/{instance.receipt.public_id}/{instance.kind}-{uuid4().hex}.{extension}"


class ReceivingEvidence(models.Model):
    KIND_CHOICES = (("delivery", "Delivery document"), ("inspection", "Inspection / acceptance document"),
                    ("supporting", "Supporting record"))
    receipt = models.ForeignKey(ReceivingReceipt, on_delete=models.PROTECT, related_name="evidence")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    file = models.FileField(upload_to=receiving_evidence_path, storage=disposal_private_storage, max_length=255)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    note = models.CharField(max_length=240)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_receiving_uploads")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at", "pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Receiving evidence cannot be replaced. Append a correction document.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Receiving evidence is retained.")


class AssetMaintenanceCase(models.Model):
    OPEN, COMPLETED, CANCELLED = "open", "completed", "cancelled"
    STATUS_CHOICES = ((OPEN, "Open"), (COMPLETED, "Completed"), (CANCELLED, "Cancelled"))
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="maintenance_cases")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=OPEN)
    state_version = models.PositiveIntegerField(default=1)
    prior_asset_status = models.CharField(max_length=16, choices=Asset.STATUS_CHOICES)
    reported_date = models.DateField()
    problem = models.TextField(max_length=4000)
    provider = models.CharField(max_length=240, blank=True)
    work_performed = models.TextField(max_length=4000, blank=True)
    documented_cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(0)])
    cost_reference = models.CharField(max_length=240, blank=True)
    finished_date = models.DateField(null=True, blank=True)
    resulting_asset_status = models.CharField(max_length=16, blank=True, choices=Asset.STATUS_CHOICES)
    closure_note = models.TextField(max_length=4000, blank=True)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_maintenance_opened")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="gso_maintenance_closed")
    closed_at = models.DateTimeField(null=True, blank=True)
    open_identity_marker = models.GeneratedField(
        expression=models.Case(models.When(status="open", then=models.Value(1)), default=models.Value(None)),
        output_field=models.PositiveSmallIntegerField(), db_persist=False, null=True,
    )

    class Meta:
        ordering = ("-opened_at", "-pk")
        default_permissions = ("view",)
        permissions = (("manage_assetmaintenancecase", "Can record asset maintenance work"),)
        constraints = (
            models.UniqueConstraint(fields=("asset", "open_identity_marker"), name="gso_one_open_maintenance"),
            models.CheckConstraint(condition=models.Q(documented_cost__isnull=True) | models.Q(documented_cost__gte=0),
                                   name="gso_maintenance_cost_nonnegative"),
        )

    def delete(self, *args, **kwargs):
        raise ValidationError("Maintenance history is retained. Cancel an open case instead.")


class AssetMaintenanceEvent(models.Model):
    case = models.ForeignKey(AssetMaintenanceCase, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_maintenance_events")
    action = models.CharField(max_length=24)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Maintenance events cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Maintenance events are retained.")


def maintenance_evidence_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"inventory/maintenance/{instance.case.public_id}/{uuid4().hex}.{extension}"


class AssetMaintenanceEvidence(models.Model):
    case = models.ForeignKey(AssetMaintenanceCase, on_delete=models.PROTECT, related_name="evidence")
    file = models.FileField(upload_to=maintenance_evidence_path, storage=disposal_private_storage, max_length=255)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    note = models.CharField(max_length=240)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_maintenance_uploads")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at", "pk")
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Maintenance evidence cannot be replaced. Append a correction document.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Maintenance evidence is retained.")


def maintenance_notice_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"inventory/maintenance_notices/{instance.case.public_id}/{instance.public_id.hex}.{extension}"


class MaintenanceCorrectionNotice(models.Model):
    """An attributable statement; never a replacement for the closed case."""
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    case = models.ForeignKey(AssetMaintenanceCase, on_delete=models.PROTECT, related_name="correction_notices")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="gso_maintenance_notices")
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    explanation = models.TextField(max_length=4000)
    source_reference = models.CharField(max_length=240)
    source_snapshot = models.JSONField()
    file = models.FileField(upload_to=maintenance_notice_path, storage=disposal_private_storage,
                            max_length=500, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ("recorded_at", "pk")
        default_permissions = ()
        constraints = (
            models.CheckConstraint(condition=(models.Q(file="", sha256="", size=0, original_filename="") |
                (~models.Q(file="") & ~models.Q(sha256="") & models.Q(size__gt=0) & ~models.Q(original_filename=""))),
                name="gso_notice_file_metadata"),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Correction notices cannot be replaced. Record a further notice instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Correction notices are retained with the original work record.")


class AssetReturnEvent(models.Model):
    transfer = models.ForeignKey(AssetTransfer, on_delete=models.PROTECT, related_name="return_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_return_events")
    action = models.CharField(max_length=24)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Return events cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Return events are retained.")


def custody_return_evidence_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"inventory/custody_returns/{instance.transfer.public_id}/{uuid4().hex}.{extension}"


class AssetReturnEvidence(models.Model):
    transfer = models.ForeignKey(AssetTransfer, on_delete=models.PROTECT, related_name="return_evidence")
    file = models.FileField(upload_to=custody_return_evidence_path, storage=disposal_private_storage, max_length=255)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    note = models.CharField(max_length=240)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_return_uploads")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at", "pk")
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Return evidence cannot be replaced. Append a correction document.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Return evidence is retained.")


class StockCount(models.Model):
    """One evidenced observation and independent decision against a pinned ledger."""
    PENDING, APPROVED, CANCELLED = "pending", "approved", "cancelled"
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    item = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, related_name="counts")
    counted_on = models.DateField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0)])
    reference = models.CharField(max_length=120)
    note = models.CharField(max_length=240)
    basis = models.JSONField()
    status = models.CharField(max_length=12, default=PENDING,
        choices=((PENDING, "Awaiting independent review"), (APPROVED, "Reviewed and recorded"), (CANCELLED, "Cancelled")))
    state_version = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_counts_recorded")
    recorded_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_counts_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=240, blank=True)
    adjustment = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="physical_count")
    pending_marker = models.GeneratedField(
        expression=models.Case(models.When(status="pending", then=models.Value(1)), default=models.Value(None)),
        output_field=models.PositiveSmallIntegerField(), db_persist=False, null=True)

    class Meta:
        ordering = ("-recorded_at", "-pk")
        default_permissions = ()
        permissions = (("record_stock_count", "Can record evidenced GSO supply counts"),
                       ("review_stock_count", "Can independently review GSO supply counts"))
        constraints = (
            models.UniqueConstraint(fields=("item", "pending_marker"), name="gso_one_pending_stock_count"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="gso_stock_count_nonnegative"),
            models.CheckConstraint(condition=models.Q(status__in=("pending", "approved", "cancelled")), name="gso_stock_count_state"),
        )


class StockCountEvent(models.Model):
    count = models.ForeignKey(StockCount, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_count_events")
    action = models.CharField(max_length=24)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    class Meta:
        ordering = ("occurred_at", "pk")
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Count events cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Count events are retained.")


def stock_count_evidence_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"inventory/stock_counts/{instance.count.public_id}/{uuid4().hex}.{extension}"


class StockCountEvidence(models.Model):
    count = models.ForeignKey(StockCount, on_delete=models.PROTECT, related_name="evidence")
    file = models.FileField(upload_to=stock_count_evidence_path, storage=disposal_private_storage, max_length=255)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    note = models.CharField(max_length=240)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_count_uploads")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at", "pk")
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Count evidence cannot be replaced. Append a correction document.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Count evidence is retained.")


def receipt_amendment_path(instance, filename):
    return f"inventory/receipt-amendments/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class ReceiptCostAmendment(models.Model):
    """Reviewed documentary cost; original inventory/Accounting values stay intact."""
    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    line = models.ForeignKey(ReceivingLine, on_delete=models.PROTECT, related_name="cost_amendments")
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors")
    basis = models.JSONField()
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    reference = models.CharField(max_length=180)
    reason = models.TextField(max_length=4000)
    file = models.FileField(storage=disposal_private_storage, upload_to=receipt_amendment_path, max_length=255)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    content_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=((PENDING,"For review"),(APPROVED,"Approved"),(REJECTED,"Rejected")), default=PENDING)
    state_version = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_cost_amendments_recorded")
    recorded_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_cost_amendments_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, max_length=4000)
    pending_line = models.GeneratedField(expression=models.Case(
        models.When(status="pending", then=models.F("line")), default=None,
        output_field=models.BigIntegerField()), output_field=models.BigIntegerField(), db_persist=False, null=True)

    class Meta:
        ordering = ("-pk",)
        permissions = (("record_receiptcostamendment", "Can record documentary receipt cost amendments"),
                       ("review_receiptcostamendment", "Can independently review documentary receipt cost amendments"))
        constraints = [models.UniqueConstraint(fields=("pending_line",), name="gso_one_pending_cost_amendment"),
            models.CheckConstraint(condition=models.Q(unit_cost__isnull=True) | models.Q(unit_cost__gte=0), name="gso_amendment_nonnegative_cost")]


class ReceiptCostAmendmentEvent(models.Model):
    amendment = models.ForeignKey(ReceiptCostAmendment, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=16)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)


def supply_requisition_path(instance, filename):
    return f"inventory/requisitions/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class SupplyRequisition(models.Model):
    """GSO's retained supplied requisition; not a new requesting-office approval."""
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    department_id = models.PositiveBigIntegerField(db_index=True)
    requesting_department_id = models.PositiveBigIntegerField(db_index=True)
    requesting_department_label = models.CharField(max_length=160)
    reference = models.CharField(max_length=120)
    requested_on = models.DateField()
    purpose = models.TextField()
    file = models.FileField(upload_to=supply_requisition_path, storage=disposal_private_storage, max_length=500)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, default="pending", choices=(
        ("pending", "Awaiting document review"), ("approved", "Reviewed; available for issue"),
        ("fulfilled", "Requested quantities issued"), ("closed", "Closed with remainder")))
    state_version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_requisitions_recorded")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_requisitions_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=240, blank=True)
    close_note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        default_permissions = ()
        permissions = (("view_supply_requisition", "Can view supplied GSO requisitions"),
            ("record_supply_requisition", "Can record and close supplied GSO requisitions"),
            ("review_supply_requisition", "Can independently review supplied GSO requisitions"))
        constraints = (models.CheckConstraint(condition=models.Q(status__in=("pending", "approved", "fulfilled", "closed")), name="gso_requisition_state"),)

    def delete(self, *args, **kwargs):
        raise ValidationError("Requisitions are retained. Close an incorrect record and retain a corrected request.")


class SupplyRequisitionLine(models.Model):
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    requisition = models.ForeignKey(SupplyRequisition, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, related_name="requisition_lines")
    item_name = models.CharField(max_length=160)
    unit = models.CharField(max_length=40)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])

    class Meta:
        ordering = ("pk",)
        default_permissions = ()
        constraints = (models.UniqueConstraint(fields=("requisition", "item"), name="gso_request_item_once"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="gso_request_line_positive"))

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Requested lines are retained unchanged. Close and record a corrected request.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Requested lines are retained.")


class SupplyFulfillment(models.Model):
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    line = models.ForeignKey(SupplyRequisitionLine, on_delete=models.PROTECT, related_name="fulfillments")
    movement = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="requisition_fulfillment")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    outcome = models.CharField(max_length=12, choices=(("issued", "Issued"), ("unavailable", "Unavailable at check")))
    recipient = models.CharField(max_length=160, blank=True)
    note = models.CharField(max_length=240)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_fulfillments")
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()
        constraints = (models.CheckConstraint(condition=(
            models.Q(outcome="issued", quantity__gt=0, movement__isnull=False)
            | models.Q(outcome="unavailable", quantity=0, movement__isnull=True)), name="gso_fulfillment_outcome"),)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Fulfillment history cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Fulfillment history is retained.")


class SupplyRequisitionEvent(models.Model):
    requisition = models.ForeignKey(SupplyRequisition, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_requisition_events")
    action = models.CharField(max_length=24)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Requisition history cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Requisition history is retained.")


def supply_return_path(instance, filename):
    return f"inventory/supply-returns/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class SupplyReturn(models.Model):
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    issue = models.ForeignKey(StockMovement, on_delete=models.PROTECT, related_name="supply_returns")
    source_allocation = models.ForeignKey(StockLotAllocation, on_delete=models.PROTECT, null=True, blank=True, related_name="supply_returns")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    reference = models.CharField(max_length=120)
    returned_by = models.CharField(max_length=160)
    observed_on = models.DateField()
    condition_note = models.CharField(max_length=240)
    cost_basis_note = models.CharField(max_length=240)
    source_snapshot = models.JSONField()
    file = models.FileField(upload_to=supply_return_path, storage=disposal_private_storage, max_length=500)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, default="pending", choices=(("pending", "Awaiting stock acceptance"),
        ("accepted", "Accepted into stock"), ("declined", "Not accepted into stock"), ("cancelled", "Cancelled")))
    state_version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_supply_returns_recorded")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_supply_returns_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=240, blank=True)
    movement = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="supply_return_case")

    class Meta:
        ordering = ("-created_at", "-pk")
        default_permissions = ()
        permissions = (("view_supply_return", "Can view documented supply returns"),
            ("record_supply_return", "Can record documented supply returns"),
            ("review_supply_return", "Can independently accept supplies returned to stock"))
        constraints = (models.CheckConstraint(condition=models.Q(quantity__gt=0), name="gso_supply_return_positive"),
            models.CheckConstraint(condition=(models.Q(status="accepted", movement__isnull=False)
                | models.Q(status__in=("pending", "declined", "cancelled"), movement__isnull=True)), name="gso_supply_return_state"))

    def delete(self, *args, **kwargs):
        raise ValidationError("Supply return records are retained.")


class SupplyReturnEvent(models.Model):
    case = models.ForeignKey(SupplyReturn, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_supply_return_events")
    action = models.CharField(max_length=24)
    occurred_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Supply return history cannot be replaced.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Supply return history is retained.")



def property_movement_path(instance, filename):
    return f"inventory/property-movements/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class PropertyMovementRecord(models.Model):
    """Reviewed source annotation; never itself a custody or Finance movement."""
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="property_movements")
    determination = models.ForeignKey(PropertyDetermination, on_delete=models.PROTECT, related_name="movement_records")
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors")
    source_kind = models.CharField(max_length=12, choices=tuple((v, v.title()) for v in ("opening", "receipt", "handoff", "return", "disposal")))
    source_key = models.CharField(max_length=100)
    receipt_line = models.ForeignKey(ReceivingLine, on_delete=models.PROTECT, null=True, blank=True, related_name="property_movements")
    transfer = models.ForeignKey(AssetTransfer, on_delete=models.PROTECT, null=True, blank=True, related_name="property_movements")
    disposal = models.ForeignKey(AssetDisposalCase, on_delete=models.PROTECT, null=True, blank=True, related_name="property_movements")
    movement_date = models.DateField()
    within_day_order = models.PositiveSmallIntegerField(default=1)
    reference = models.CharField(max_length=180)
    item_number = models.CharField(max_length=100, blank=True)
    office_officer_label = models.CharField(max_length=240, blank=True)
    stock_delta = models.SmallIntegerField(default=0)
    opening_quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    remarks = models.CharField(max_length=500)
    source_snapshot = models.JSONField()
    file = models.FileField(upload_to=property_movement_path, storage=disposal_private_storage, max_length=500)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, default="pending", choices=tuple((v, v.title()) for v in ("pending", "verified", "rejected", "cancelled")))
    state_version = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_property_movements_recorded")
    recorded_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_property_movements_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    pending_asset = models.GeneratedField(expression=models.Case(models.When(status="pending", then=models.F("asset_id")), default=models.Value(None)), output_field=models.BigIntegerField(null=True), db_persist=False)

    class Meta:
        ordering = ("movement_date", "within_day_order", "pk")
        default_permissions = ()
        permissions = (("view_property_movement", "Can view documented property movements"),
            ("record_property_movement", "Can record property movement sources and openings"),
            ("review_property_movement", "Can independently verify property movement documents"))
        constraints = [
            models.UniqueConstraint(fields=("pending_asset",), name="gso_one_pending_property_move"),
            models.CheckConstraint(condition=(
                models.Q(source_kind="opening", receipt_line__isnull=True, transfer__isnull=True, disposal__isnull=True)
                | models.Q(source_kind="receipt", receipt_line__isnull=False, transfer__isnull=True, disposal__isnull=True)
                | models.Q(source_kind__in=("handoff", "return"), receipt_line__isnull=True, transfer__isnull=False, disposal__isnull=True)
                | models.Q(source_kind="disposal", receipt_line__isnull=True, transfer__isnull=True, disposal__isnull=False)),
                name="gso_property_move_source"),
            models.CheckConstraint(condition=(
                models.Q(source_kind="opening", stock_delta=0, opening_quantity__in=(0, 1), opening_quantity__isnull=False, within_day_order=0)
                | (~models.Q(source_kind="opening") & models.Q(opening_quantity__isnull=True, within_day_order__gt=0) & (
                    models.Q(source_kind="receipt", stock_delta=1)
                    | models.Q(source_kind__in=("handoff", "disposal"), stock_delta__in=(-1, 0))
                    | models.Q(source_kind="return", stock_delta__in=(0, 1))))), name="gso_property_move_effect"),
            models.CheckConstraint(condition=models.Q(unit_cost__isnull=True) | models.Q(unit_cost__gte=0), name="gso_property_move_cost"),
            models.CheckConstraint(condition=~models.Q(status__in=("verified", "rejected")) | (
                models.Q(decided_by__isnull=False, decided_at__isnull=False) & ~models.Q(decided_by=models.F("recorded_by"))), name="gso_property_move_independent"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            mutable = {"status", "state_version", "decided_by_id", "decided_at", "decision_note"}
            if not getattr(self, "_workflow_write", False) or any(
                getattr(prior, field.attname) != getattr(self, field.attname)
                for field in self._meta.concrete_fields if not field.generated and field.attname not in mutable
            ):
                raise ValidationError("Retain property movement sources; use a reviewed successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain property movement sources and their history.")


class PropertyMovementEvent(models.Model):
    movement = models.ForeignKey(PropertyMovementRecord, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_property_movement_events")
    action = models.CharField(max_length=16)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Property movement events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain property movement events.")


def receipt_quantity_correction_path(instance, filename):
    return f"inventory/receipt-quantity-corrections/{instance.public_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class ReceiptQuantityCorrection(models.Model):
    """Retained clerical overstatement, never a physical return or journal reversal."""
    PENDING, APPROVED, REJECTED, CANCELLED = "pending", "approved", "rejected", "cancelled"
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    line = models.ForeignKey(ReceivingLine, on_delete=models.PROTECT, related_name="quantity_corrections")
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    basis = models.JSONField()
    reference = models.CharField(max_length=180)
    reason = models.TextField(max_length=4000)
    file = models.FileField(storage=disposal_private_storage, upload_to=receipt_quantity_correction_path, max_length=500)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    content_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=12, default=PENDING, choices=tuple(
        (value, value.title()) for value in (PENDING, APPROVED, REJECTED, CANCELLED)))
    state_version = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gso_quantity_corrections_recorded")
    recorded_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="gso_quantity_corrections_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, max_length=4000)
    adjustment = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="receipt_quantity_correction")
    asset_event = models.OneToOneField(AssetAuditEvent, on_delete=models.PROTECT, null=True, blank=True, related_name="receipt_quantity_correction")
    pending_line = models.GeneratedField(expression=models.Case(
        models.When(status="pending", then=models.F("line_id")), default=None,
        output_field=models.BigIntegerField()), output_field=models.BigIntegerField(), db_persist=False, null=True)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()
        permissions = (("record_receipt_quantity_correction", "Can record clerical receipt quantity corrections"),
                       ("review_receipt_quantity_correction", "Can independently review clerical receipt quantity corrections"))
        constraints = [
            models.UniqueConstraint(fields=("pending_line",), name="gso_one_pending_qty_correction"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="gso_qty_correction_positive"),
            models.CheckConstraint(condition=(
                models.Q(status="approved", decided_by__isnull=False, decided_at__isnull=False)
                & ~models.Q(decided_by=models.F("recorded_by")) & (
                    models.Q(adjustment__isnull=False, asset_event__isnull=True)
                    | models.Q(adjustment__isnull=True, asset_event__isnull=False)))
                | models.Q(status__in=("pending", "rejected", "cancelled"), adjustment__isnull=True, asset_event__isnull=True),
                name="gso_qty_correction_result"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = ("public_id", "line_id", "predecessor_id", "quantity", "basis", "reference", "reason",
                         "file", "original_filename", "sha256", "size", "content_checksum", "recorded_by_id", "recorded_at")
            if not getattr(self, "_workflow_write", False) or any(
                    getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Retain the correction content; use its reviewed workflow.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain receipt quantity correction history.")


class ReceiptQuantityCorrectionEvent(models.Model):
    correction = models.ForeignKey(ReceiptQuantityCorrection, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=16)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Receipt quantity correction events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain receipt quantity correction events.")
