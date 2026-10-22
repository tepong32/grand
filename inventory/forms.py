from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from pathlib import Path
from .access import department_model
from .models import (
    Asset, AssetDisposalCase, AssetVerificationFinding, AssetVerificationRecord,
    AssetVerificationRound, ConsumableItem, StockMovement,
)


MAX_DISPOSAL_FILE_BYTES = 15 * 1024 * 1024


class StockHistoryFilterForm(forms.Form):
    q = forms.CharField(label="Supply item or source reference", required=False, max_length=100)
    from_date = forms.DateField(label="Recorded from", required=False,
        widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(label="Recorded through", required=False,
        widget=forms.DateInput(attrs={"type": "date"}))
    kind = forms.ChoiceField(label="Movement", required=False,
        choices=(("", "All movements"),) + StockMovement.KIND_CHOICES)

    def clean(self):
        data = super().clean()
        start, end = data.get("from_date"), data.get("to_date")
        if start and end and start > end:
            self.add_error("to_date", "Choose an end date on or after the start date.")
        return data


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultiFileField, self).clean(item, initial) for item in files]


def _validate_disposal_upload(upload):
    extension = Path(upload.name).suffix.lower()
    if upload.size > MAX_DISPOSAL_FILE_BYTES:
        raise ValidationError("Each file must be 15 MB or smaller.")
    if extension in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            image = Image.open(upload)
            image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise ValidationError("This image could not be opened. Try a JPG, PNG, or WebP image.")
        finally:
            upload.seek(0)
    elif extension == ".pdf":
        if upload.read(5) != b"%PDF-":
            upload.seek(0)
            raise ValidationError("This file does not appear to be a valid PDF.")
        upload.seek(0)
    else:
        raise ValidationError("Use a JPG, PNG, WebP, or PDF file.")
    return upload


class AssetForm(forms.ModelForm):
    assigned_department = forms.TypedChoiceField(
        choices=(), required=False, coerce=int, empty_value=None,
        label="Assigned department",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and hasattr(self.instance, "receiving_line"):
            from .services import RECEIVED_ASSET_FACTS
            for name in RECEIVED_ASSET_FACTS:
                self.fields[name].disabled = True
                self.fields[name].help_text = (
                    "Retained from accepted receiving. Documentary cost corrections use receipt amendments."
                )
        self.fields["status"].choices = [
            (value, label) for value, label in Asset.STATUS_CHOICES if value not in (Asset.RETIRED, Asset.ENTRY_VOID)
        ]
        model = department_model()
        if model is None:
            self.fields["assigned_department"].choices = [("", "Department directory is unavailable")]
        else:
            departments = model.objects.exclude(name="---select one---").order_by("name")
            self.fields["assigned_department"].choices = [
                (str(department.pk), department.name) for department in departments
            ]
            if self.instance and self.instance.assigned_department_id:
                self.fields["assigned_department"].initial = str(self.instance.assigned_department_id)
        self.order_fields((
            "asset_kind", "inventory_class", "item_type", "asset_name", "category", "property_tag", "brand", "model_number", "serial_number",
            "plate_number", "engine_number", "chassis_number", "registration_due",
            "obr_reference", "purchase_order_reference", "voucher_reference", "journal_reference", "fund_code",
            "coa_account_code", "coa_account_title", "coa_basis", "purchase_date", "supplier", "unit_cost", "quantity",
            "assigned_department", "assigned_office", "status", "returned_date", "notes",
        ))

    class Meta:
        model = Asset
        fields = (
            "asset_kind", "inventory_class", "item_type", "asset_name", "category", "property_tag", "brand", "model_number", "serial_number",
            "plate_number", "engine_number", "chassis_number", "registration_due",
            "obr_reference", "purchase_order_reference", "voucher_reference", "journal_reference", "fund_code",
            "coa_account_code", "coa_account_title", "coa_basis", "purchase_date", "supplier", "unit_cost", "quantity",
            "assigned_office", "status", "returned_date", "notes",
        )
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "returned_date": forms.DateInput(attrs={"type": "date"}),
            "registration_due": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "inventory_class": "Choose the closest reporting group. Accounting must confirm the official COA mapping separately.",
            "item_type": "Choose the closest item type; use Other for an unlisted item and describe it below.",
            "category": "Optional detail or legacy category. This is not the official accounting classification.",
            "coa_account_code": "Enter only the account code confirmed by Accounting; leave blank until reviewed.",
            "coa_account_title": "Use the title from the locally approved LGU chart of accounts.",
            "coa_basis": "Record the reviewer or approved mapping reference used for this classification.",
        }

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self.instance.pk and quantity == self.instance.quantity:
            return quantity
        if quantity != 1:
            raise ValidationError("Record one tagged equipment item or vehicle per asset record.")
        return quantity

    def clean(self):
        cleaned = super().clean()
        asset_kind = cleaned.get("asset_kind")
        inventory_class = cleaned.get("inventory_class")
        item_type = cleaned.get("item_type")
        if asset_kind == Asset.VEHICLE:
            if inventory_class != Asset.CLASS_TRANSPORT:
                self.add_error("inventory_class", "Class vehicles as transportation equipment.")
            if item_type != "motor_vehicle":
                self.add_error("item_type", "Choose Motor vehicle for a transport vehicle record.")
        elif item_type == "motor_vehicle":
            self.add_error("item_type", "Choose Transport vehicle as the asset type for a motor vehicle.")
        if item_type in Asset.FURNITURE_ITEM_TYPES and inventory_class != Asset.CLASS_FURNITURE:
            self.add_error("inventory_class", "Class desks, chairs, tables, cabinets, and fixtures as furniture and fixtures.")
        if inventory_class == Asset.CLASS_FURNITURE and item_type not in Asset.FURNITURE_ITEM_TYPES | {"other"}:
            self.add_error("item_type", "Choose a furniture or fixture item type, or Other if the item needs review.")
        if cleaned.get("status") == Asset.TRANSFERRED and not cleaned.get("returned_date"):
            self.add_error("returned_date", "Add the transfer or return date for a transferred asset.")
        return cleaned


class AssetTransferForm(forms.Form):
    destination_department = forms.TypedChoiceField(choices=(), coerce=int, label="Receiving department")
    destination_custodian = forms.CharField(max_length=160, label="Receiving office / custodian")
    transfer_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(max_length=240, label="Reason for handoff")
    reference = forms.CharField(max_length=120, required=False, label="PAR / ICS / other reference")

    def __init__(self, *args, asset=None, **kwargs):
        self.asset = asset
        super().__init__(*args, **kwargs)
        model = department_model()
        if model is None:
            self.fields["destination_department"].choices = [("", "Department directory unavailable")]
        else:
            departments = model.objects.exclude(name="---select one---").order_by("name")
            self.fields["destination_department"].choices = [(str(row.pk), row.name) for row in departments]

    def clean(self):
        cleaned = super().clean()
        if (self.asset and cleaned.get("destination_department") == self.asset.assigned_department_id
                and cleaned.get("destination_custodian", "").strip() == self.asset.assigned_office.strip()):
            raise ValidationError("Choose a different department or custodian.")
        return cleaned


class TransferCancellationForm(forms.Form):
    reason = forms.CharField(max_length=240, label="Why is this handoff being cancelled?")


class AssetVerificationRoundForm(forms.Form):
    title = forms.CharField(
        max_length=160, label="Verification round name",
        help_text="Example: 2026 annual physical inventory check.",
    )
    as_of_date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}),
        label="Physical count date",
        help_text="Use the date the inventory committee treats the physical count as covering.",
    )

    def clean_as_of_date(self):
        as_of_date = self.cleaned_data["as_of_date"]
        if as_of_date > timezone.localdate():
            raise ValidationError("The physical count date cannot be in the future.")
        return as_of_date


class AssetVerificationRecordForm(forms.Form):
    result = forms.ChoiceField(choices=tuple(choice for choice in AssetVerificationRecord.RESULT_CHOICES if choice[0] != AssetVerificationRecord.NOT_CHECKED))
    observed_department = forms.CharField(required=False, max_length=160, label="Department where found")
    observed_office = forms.CharField(required=False, max_length=160, label="Room / office / current custodian")
    condition = forms.ChoiceField(choices=(("", "Select if assessed"),) + AssetVerificationRecord.CONDITION_CHOICES, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Discrepancy or follow-up notes")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("result") in (AssetVerificationRecord.DISCREPANCY, AssetVerificationRecord.NOT_FOUND) and not cleaned.get("notes", "").strip():
            self.add_error("notes", "Add a brief note so GSO knows what needs follow-up.")
        return cleaned


class AssetVerificationFollowUpForm(forms.Form):
    status = forms.ChoiceField(choices=(
        (AssetVerificationRecord.FOLLOW_UP_RESOLVED, "Resolved"),
        (AssetVerificationRecord.FOLLOW_UP_ACCEPTED, "Reviewed; difference accepted"),
    ))
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="What was checked or decided?")

    def clean_note(self):
        note = self.cleaned_data["note"].strip()
        if not note:
            raise ValidationError("Enter a brief follow-up note.")
        return note


class AssetVerificationFindingForm(forms.Form):
    asset_name = forms.CharField(max_length=180, label="Item found")
    property_tag = forms.CharField(required=False, max_length=100, label="Property tag / asset number")
    serial_number = forms.CharField(required=False, max_length=120)
    found_department = forms.CharField(required=False, max_length=160, label="Department where found")
    found_office = forms.CharField(required=False, max_length=160, label="Room / office / custodian")
    condition = forms.ChoiceField(
        choices=(("", "Select if assessed"),) + AssetVerificationRecord.CONDITION_CHOICES,
        required=False,
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="What should GSO review?")


class AssetVerificationFindingReviewForm(forms.Form):
    status = forms.ChoiceField(choices=tuple(choice for choice in AssetVerificationFinding.STATUS_CHOICES if choice[0] != AssetVerificationFinding.PENDING))
    related_asset = forms.ModelChoiceField(queryset=Asset.objects.none(), required=False, label="Related asset record")
    resolution_note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Review note")

    def __init__(self, *args, verification_round, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["related_asset"].queryset = Asset.objects.filter(
            department_id=verification_round.department_id,
        ).order_by("asset_name", "pk")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") in (AssetVerificationFinding.REGISTERED, AssetVerificationFinding.DUPLICATE) and not cleaned.get("related_asset"):
            self.add_error("related_asset", "Select the asset record that was created or is the duplicate.")
        if not cleaned.get("resolution_note", "").strip():
            self.add_error("resolution_note", "Enter the review decision or next step.")
        return cleaned


class AssetAccountingImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Accounting asset list (CSV)",
        help_text="Use the downloadable template. The file is retained as normalized rows and a SHA-256 fingerprint, not as a public download.",
    )

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if upload.size > 10 * 1024 * 1024:
            raise ValidationError("The CSV file must be 10 MB or smaller.")
        if Path(upload.name).suffix.lower() != ".csv":
            raise ValidationError("Upload a .csv file.")
        return upload


class AssetDisposalRequestForm(forms.Form):
    reason = forms.CharField(max_length=240, label="Why is the asset being considered for disposal?")
    condition_details = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}), label="Describe its condition or problem",
    )
    photos = MultiFileField(
        label="Asset condition photo(s)",
        widget=MultiFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "capture": "environment"}),
        help_text="Take a photo with your phone or choose existing images. Up to 5 photos, 15 MB each.",
    )
    signed_request = forms.FileField(
        label="Signed disposal request form",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,image/jpeg,image/png,image/webp"}),
        help_text="Upload a scanned PDF or photo of the signed form.",
    )
    supporting_documents = MultiFileField(
        required=False, label="Other supporting documents",
        widget=MultiFileInput(attrs={"accept": "application/pdf,image/jpeg,image/png,image/webp"}),
        help_text="Optional inspection notes, repair estimates, or other records. Up to 8 files.",
    )

    def clean_photos(self):
        files = self.cleaned_data["photos"]
        if not 1 <= len(files) <= 5:
            raise ValidationError("Attach between 1 and 5 condition photos.")
        for upload in files:
            _validate_disposal_upload(upload)
        return files

    def clean_signed_request(self):
        return _validate_disposal_upload(self.cleaned_data["signed_request"])

    def clean_supporting_documents(self):
        files = self.cleaned_data["supporting_documents"]
        if len(files) > 8:
            raise ValidationError("Attach up to 8 supporting files.")
        for upload in files:
            _validate_disposal_upload(upload)
        return files

    def clean(self):
        cleaned = super().clean()
        uploads = cleaned.get("photos", []) + ([cleaned["signed_request"]] if cleaned.get("signed_request") else []) + cleaned.get("supporting_documents", [])
        if sum(upload.size for upload in uploads) > 50 * 1024 * 1024:
            raise ValidationError("The total upload size must be 50 MB or less.")
        return cleaned


class AssetDisposalReviewForm(forms.Form):
    action = forms.ChoiceField(choices=())
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Review note")
    authority_reference = forms.CharField(
        required=False, max_length=160, label="Approval / authority reference",
        help_text="Required when choosing Authorized for disposal.",
    )
    disposal_method = forms.ChoiceField(
        choices=AssetDisposalCase.DISPOSAL_METHOD_CHOICES, required=False,
        help_text="Required when recording a completed disposal.",
    )
    disposal_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        label="Completed disposal date", help_text="Required when recording a completed disposal.",
    )
    completion_reference = forms.CharField(
        required=False, max_length=160, label="Completion / receipt reference",
        help_text="Required when recording a completed disposal.",
    )
    authority_document = forms.FileField(
        required=False, label="Approval / authority document",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,image/jpeg,image/png,image/webp"}),
    )
    completion_document = forms.FileField(
        required=False, label="Disposal completion evidence",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,image/jpeg,image/png,image/webp"}),
    )
    supporting_documents = MultiFileField(
        required=False, label="Add supporting documents",
        widget=MultiFileInput(attrs={"accept": "application/pdf,image/jpeg,image/png,image/webp"}),
        help_text="Optional scan of inspection, appraisal, approval, or disposal records. Up to 8 files.",
    )

    def __init__(self, *args, case, **kwargs):
        self.case = case
        super().__init__(*args, **kwargs)
        choices = {
            AssetDisposalCase.SUBMITTED: (AssetDisposalCase.UNDER_REVIEW, AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.REJECTED),
            AssetDisposalCase.UNDER_REVIEW: (AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED, AssetDisposalCase.REJECTED),
            AssetDisposalCase.NEEDS_INFORMATION: (AssetDisposalCase.UNDER_REVIEW, AssetDisposalCase.REJECTED),
            AssetDisposalCase.AUTHORIZED: (AssetDisposalCase.DISPOSED,),
        }.get(case.status, ())
        self.fields["action"].choices = [(value, dict(AssetDisposalCase.STATUS_CHOICES)[value]) for value in choices]
        self.fields["disposal_method"].choices = AssetDisposalCase.DISPOSAL_METHOD_CHOICES

    def clean_supporting_documents(self):
        files = self.cleaned_data["supporting_documents"]
        if len(files) > 8:
            raise ValidationError("Attach up to 8 supporting files.")
        for upload in files:
            _validate_disposal_upload(upload)
        return files

    def clean_authority_document(self):
        upload = self.cleaned_data.get("authority_document")
        return _validate_disposal_upload(upload) if upload else upload

    def clean_completion_document(self):
        upload = self.cleaned_data.get("completion_document")
        return _validate_disposal_upload(upload) if upload else upload

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        if action == AssetDisposalCase.AUTHORIZED and not cleaned.get("authority_reference", "").strip():
            self.add_error("authority_reference", "Record the approval or authority reference before authorizing disposal.")
        if action == AssetDisposalCase.AUTHORIZED and not cleaned.get("authority_document") and not self.case.attachments.filter(kind="authority").exists():
            self.add_error("authority_document", "Attach the approval or authority document before authorizing disposal.")
        if action == AssetDisposalCase.DISPOSED:
            if not cleaned.get("disposal_method"):
                self.add_error("disposal_method", "Choose how the asset was disposed.")
            if not cleaned.get("disposal_date"):
                self.add_error("disposal_date", "Enter the date disposal was completed.")
            if not cleaned.get("completion_reference", "").strip():
                self.add_error("completion_reference", "Record a completion or receipt reference.")
            if not cleaned.get("completion_document") and not self.case.attachments.filter(kind="completion").exists():
                self.add_error("completion_document", "Attach evidence that the disposal was completed.")
        uploaded = list(cleaned.get("supporting_documents", []))
        uploaded.extend(file for file in (cleaned.get("authority_document"), cleaned.get("completion_document")) if file)
        if sum(upload.size for upload in uploaded) > 50 * 1024 * 1024:
            raise ValidationError("The total upload size must be 50 MB or less.")
        return cleaned


class AssetDisposalResponseForm(forms.Form):
    response = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}), label="Response to GSO")
    supporting_documents = MultiFileField(
        required=False, label="Additional supporting documents",
        widget=MultiFileInput(attrs={"accept": "application/pdf,image/jpeg,image/png,image/webp"}),
        help_text="Optional scan or photo requested by GSO. Up to 8 files.",
    )

    def clean_supporting_documents(self):
        files = self.cleaned_data["supporting_documents"]
        if len(files) > 8:
            raise ValidationError("Attach up to 8 supporting files.")
        for upload in files:
            _validate_disposal_upload(upload)
        return files

    def clean(self):
        cleaned = super().clean()
        if sum(upload.size for upload in cleaned.get("supporting_documents", [])) > 50 * 1024 * 1024:
            raise ValidationError("The total upload size must be 50 MB or less.")
        return cleaned


class ConsumableItemForm(forms.ModelForm):
    class Meta:
        model = ConsumableItem
        fields = ("name", "category", "unit", "use_fifo", "minimum_stock", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_use_fifo(self):
        use_fifo = self.cleaned_data["use_fifo"]
        if self.instance.pk and self.instance.use_fifo != use_fifo and self.instance.movements.exists():
            raise ValidationError("FIFO tracking cannot be changed after stock movements exist.")
        return use_fifo

    def clean_name(self):
        name = self.cleaned_data["name"]
        if self.instance.pk and self.instance.movements.exists() and name != self.instance.name:
            raise ValidationError("The name cannot change after stock movements exist; create a new item instead.")
        return name

    def clean_unit(self):
        unit = self.cleaned_data["unit"]
        if self.instance.pk and self.instance.movements.exists() and unit != self.instance.unit:
            raise ValidationError("The unit cannot change after stock movements exist; create a new item instead.")
        return unit


class StockMovementRequestForm(forms.Form):
    request_token = forms.CharField(widget=forms.HiddenInput)


class StockReceiptForm(StockMovementRequestForm):
    quantity = forms.DecimalField(min_value=0.001, max_digits=12, decimal_places=3)
    unit_cost = forms.DecimalField(required=False, min_value=0, max_digits=13, decimal_places=2)
    reference = forms.CharField(max_length=120, required=False, label="Delivery / purchase reference")
    reason = forms.CharField(max_length=240, required=False, label="Note")


class StockIssueForm(StockMovementRequestForm):
    quantity = forms.DecimalField(min_value=0.001, max_digits=12, decimal_places=3)
    department = forms.TypedChoiceField(choices=(), coerce=int, label="Receiving department")
    recipient = forms.CharField(max_length=160, label="Received by")
    reference = forms.CharField(max_length=120, required=False, label="Requisition / issue reference")
    reason = forms.CharField(max_length=240, required=False, label="Purpose / note")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = department_model()
        if model is None:
            self.fields["department"].choices = [("", "Department directory unavailable")]
        else:
            qs = model.objects.exclude(name="---select one---").order_by("name")
            self.fields["department"].choices = [(str(row.pk), row.name) for row in qs]


class StockAdjustmentForm(StockMovementRequestForm):
    direction = forms.ChoiceField(choices=(("in", "Increase balance"), ("out", "Decrease balance")))
    quantity = forms.DecimalField(min_value=0.001, max_digits=12, decimal_places=3)
    reason = forms.CharField(max_length=240, label="Reason for adjustment")
