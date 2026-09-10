import hashlib
import io
import json
import zipfile
from datetime import date
from pathlib import Path

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from . import test_cash_flows
from .models import FinanceStatementNoteSet, ReportDefinition, ReportReferenceComparison
from .services import create_manual_run
from .statement_bundle import statement_bundle
from .statement_services import (create_note_set, submit_note_set, review_note_set,
    comparison_generated_values, submit_reference_comparison, review_reference_comparison,
    note_set_snapshot, note_set_source_snapshot, snapshot_checksum)


class FourStatementPackageTests(TestCase):
    databases = {"default", "finance"}
    post = test_cash_flows.CashFlowReportingTests.post

    def setUp(self):
        test_cash_flows.CashFlowReportingTests.setUp(self)
        for actor, codes in ((self.maker, ("prepare_statement_notes", "prepare_reference_comparisons", "export_statement_packages", "download_reports")),
                             (self.checker, ("review_statement_notes", "review_reference_comparisons"))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="reporting", codename__in=codes))
            for cache in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
                actor.__dict__.pop(cache, None)
        self.post("COLLECTION", [("cash", 100, 0, "op_taxes"), ("revenue", 0, 100, "")])
        self.runs = {}
        for kind in ("position", "performance", "net_assets", "cash_flow"):
            definition = ReportDefinition.objects.get(department=self.department, dataset_key="finance_statement_" + kind)
            self.runs[kind + "_run"] = create_manual_run(definition, definition.current_template, "xlsx",
                date(2027, 1, 1), date(2027, 3, 31), {}, self.maker)

    def notes(self):
        notes = create_note_set(department=self.department, actor=self.maker, data={"title": "Synthetic quarterly financial statements"}, **self.runs)
        for item in notes.notes.all():
            item.disclosure_text = "Synthetic working disclosure checked against the posted source."
            item.source_reference = "Synthetic quarterly schedule"
            item.save()
        submit_note_set(notes, self.maker)
        return review_note_set(notes, self.checker, action="accept_working", note="All four statements checked")

    def test_posted_collection_to_four_original_files_and_printable_notes(self):
        notes = self.notes()
        payload = statement_bundle(notes)
        self.assertEqual(payload, statement_bundle(notes))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(len(archive.namelist()), 6)
            manifest = json.loads(archive.read("manifest.json"))
            for kind, run in self.runs.items():
                name = "statements/" + kind.removesuffix("_run") + ".xlsx"
                self.assertEqual(archive.read(name), Path(run.output_file.path).read_bytes())
            self.assertIn(b"All four statements checked", archive.read("notes.html"))
            for record in manifest["files"]:
                self.assertEqual(hashlib.sha256(archive.read(record["path"])).hexdigest(), record["sha256"])
        self.client.force_login(self.maker)
        with self.settings(GRAND_EXPORT_ROOT=Path(self.media) / "exports"):
            response = self.client.get(reverse("reporting:statement_bundle_export", args=[notes.public_id]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, payload)
        self.maker.user_permissions.remove(Permission.objects.get(content_type__app_label="reporting", codename="download_reports"))
        self.assertEqual(self.client.get(reverse("reporting:statement_bundle_export", args=[notes.public_id])).status_code, 403)
        prior = self.runs["cash_flow_run"]
        Path(prior.output_file.path).write_bytes(b"altered artifact")
        # The issued package is itself a retained copy, independent of later live files.
        self.assertEqual(statement_bundle(notes), payload)
        FinanceStatementNoteSet.objects.filter(pk=notes.pk).update(cash_flow_run=self.runs["net_assets_run"])
        with self.assertRaisesMessage(ValidationError, "identities differ"):
            statement_bundle(notes)
        FinanceStatementNoteSet.objects.filter(pk=notes.pk).update(cash_flow_run=prior)
        notes.refresh_from_db()
        Path(notes.bundle_file.path).write_bytes(b"altered package")
        with self.assertRaisesMessage(ValidationError, "SHA-256"):
            statement_bundle(notes)

    def test_cash_and_equity_reference_rows_include_each_fund_and_comparative(self):
        for field in ("cash_flow_run", "net_assets_run"):
            run = self.runs[field]
            values = comparison_generated_values(run)
            self.assertEqual(len(values), len(run.dataset_snapshot["rows"]) * 2)
            comparison = ReportReferenceComparison.objects.create(run=run, version=1,
                reference_label="Synthetic signed comparison", reference_kind="pdf",
                reference_file=SimpleUploadedFile("reference.pdf", b"synthetic reference"),
                signed_copy=True, redaction_confirmed=True, authority_reference="Synthetic authority",
                local_acceptance_note="Synthetic source check", reference_values=values, created_by=self.maker)
            submit_reference_comparison(comparison, self.maker)
            reviewed = review_reference_comparison(comparison, self.checker, approve=True, note="Every row checked")
            self.assertEqual(reviewed.status, ReportReferenceComparison.RECONCILED)

    def test_new_package_requires_four_members_and_exact_period(self):
        with self.assertRaisesMessage(ValidationError, "New packages require"):
            create_note_set(department=self.department, actor=self.maker, data={},
                position_run=self.runs["position_run"], performance_run=self.runs["performance_run"])
        run = self.runs["cash_flow_run"]
        # Simulate a genuinely different stored reporting period, not just a caller object.
        type(run).objects.filter(pk=run.pk).update(period_end=date(2027, 3, 30))
        with self.assertRaisesMessage(ValidationError, "period exactly"):
            create_note_set(department=self.department, actor=self.maker, data={}, **self.runs)

    def test_individually_reconciled_reports_cannot_mix_different_posting_cutoffs(self):
        self.post("LATER-COLLECTION", [("cash", 25, 0, "op_taxes"), ("revenue", 0, 25, "")])
        prior = self.runs["cash_flow_run"]
        self.runs["cash_flow_run"] = create_manual_run(prior.definition, prior.template_version, "xlsx",
            prior.period_start, prior.period_end, {}, self.maker)
        self.assertTrue(all(run.control_status == "reconciled" for run in self.runs.values()))
        with self.assertRaisesMessage(ValidationError, "retained posted journals differ"):
            self.notes()

    def test_filtered_position_cannot_masquerade_as_complete_package_member(self):
        definition = self.runs["position_run"].definition
        definition.filters = {"line_code": "assets"}
        definition.save(update_fields=("filters",))
        self.runs["position_run"] = create_manual_run(definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.maker)
        self.assertEqual(self.runs["position_run"].control_status, "reconciled")
        with self.assertRaisesMessage(ValidationError, "keep every mapped financial row"):
            self.notes()

    def test_legacy_two_member_snapshot_stays_exact_but_cannot_be_resubmitted_incomplete(self):
        # Historical persisted shape: no new members, source keys, or bundle fields.
        notes = FinanceStatementNoteSet.objects.create(department=self.department, title="Historical notes",
            period_start=date(2027, 1, 1), period_end=date(2027, 3, 31), version=1,
            position_run=self.runs["position_run"], performance_run=self.runs["performance_run"], created_by=self.maker)
        old_source = {key: value for key, value in note_set_source_snapshot(notes).items()
            if key in {"position_run", "performance_run"}}
        notes.source_snapshot = old_source
        notes.snapshot_checksum = snapshot_checksum(note_set_snapshot(notes))
        notes.save()
        original = notes.snapshot_checksum
        notes.refresh_from_db()
        self.assertEqual(note_set_source_snapshot(notes), old_source)
        self.assertEqual(snapshot_checksum(note_set_snapshot(notes)), original)
        with self.assertRaisesMessage(ValidationError, "all four"):
            submit_note_set(notes, self.maker)
