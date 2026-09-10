import hashlib
from datetime import date
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase
from openpyxl import load_workbook

from accounting.models import Fund
from . import test_statement_bundle
from .datasets import build_dataset_with_evidence
from .models import ReportDefinition
from .services import create_manual_run


class StatementFundTests(TestCase):
    databases = {"default", "finance"}
    post = test_statement_bundle.FourStatementPackageTests.post
    notes = test_statement_bundle.FourStatementPackageTests.notes

    def setUp(self):
        test_statement_bundle.FourStatementPackageTests.setUp(self)
        self.original_runs = dict(self.runs)
        self.fund = Fund.objects.create(**self.owner, code="SEF", name="Special Education Fund")
        self.post("SEF-OPEN", [("cash", 900, 0, ""), ("equity", 0, 900, "")], year=2026, opening=True)
        self.post("SEF-RECEIPT", [("cash", 70, 0, "op_taxes"), ("revenue", 0, 70, "")])

    def generate(self, filters):
        for field, prior in self.original_runs.items():
            definition = prior.definition
            definition.filters = filters
            definition.full_clean()
            definition.save(update_fields=("filters",))
            self.runs[field] = create_manual_run(definition, definition.current_template, "xlsx",
                date(2027, 1, 1), date(2027, 3, 31), {}, self.maker)
        return self.runs

    def test_fund_sources_amounts_complete_files_and_four_statement_package(self):
        for filters, expected_funds, closing, result in (
            ({"fund_code__exact": "GF"}, {"GF"}, "500.00", "100.00"),
            ({"fund_code": "SEF"}, {"SEF"}, "970.00", "70.00"),
            ({"fund_code__in": ["GF", "SEF"]}, {"GF", "SEF"}, "1470.00", "170.00"),
            ({}, {"GF", "SEF"}, "1470.00", "170.00"),
        ):
            with self.subTest(filters=filters):
                runs = self.generate(filters)
                self.assertEqual(runs["position_run"].control_totals["assets"], closing)
                self.assertEqual(runs["performance_run"].control_totals["operating_result"], result)
                self.assertEqual(runs["net_assets_run"].control_totals["closing"], closing)
                self.assertEqual(set(runs["cash_flow_run"].control_totals["funds"]), expected_funds)
                for field, run in runs.items():
                    self.assertEqual(run.control_status, "reconciled")
                    self.assertEqual(run.parameters["_definition_snapshot"]["filters"], filters)
                    sources = run.source_records.filter(source_model="JournalEntry")
                    self.assertEqual({source.snapshot["fund"] for source in sources}, expected_funds)
                    self.assertEqual(sources.count(), len(expected_funds) * (1 if field == "performance_run" else 2))
                    workbook = load_workbook(run.output_file.path, data_only=True)
                    exported = list(workbook.active.values)
                    self.assertIn("(Funds: ", workbook.active["A2"].value)
                    for row in run.dataset_snapshot["rows"]:
                        self.assertTrue(any(row["line_code"] in values and float(row["amount"]) in values
                            for values in exported), row)
                    workbook.close()
                self.notes()
        for run in self.original_runs.values():
            run.refresh_from_db()
            self.assertEqual(run.parameters["_definition_snapshot"]["filters"], {})
            self.assertEqual(hashlib.sha256(Path(run.output_file.path).read_bytes()).hexdigest(), run.checksum)

    def test_invalid_and_row_hiding_configuration_is_rejected_for_every_statement(self):
        invalid = (("filters", {"line_code": "assets"}), ("filters", {"fund_code__contains": "G"}),
            ("filters", {"fund_code__in": []}), ("filters", {"fund_code__in": "GF"}),
            ("filters", {"fund_code": ""}), ("filters", {"fund_code": "GF", "fund_code__in": ["SEF"]}),
            ("selected_fields", ["amount"]), ("group_by", ["line_code"]),
            ("totals", ["amount"]), ("sort_by", ["amount"]))
        for run in self.original_runs.values():
            for field, value in invalid:
                with self.subTest(dataset=run.definition.dataset_key, field=field, value=value):
                    definition = ReportDefinition.objects.get(pk=run.definition_id)
                    setattr(definition, field, value)
                    with self.assertRaises(ValidationError):
                        definition.full_clean()
                    with self.assertRaises(ValueError):
                        build_dataset_with_evidence(definition, run.period_start, run.period_end, {})
            definition = ReportDefinition.objects.get(pk=run.definition_id)
            definition.filters = {"fund_code__in": ["GF", "UNKNOWN"]}
            with self.assertRaisesMessage(ValueError, "must exist in this Accounting office"):
                build_dataset_with_evidence(definition, run.period_start, run.period_end, {})

    def test_definition_form_saves_exact_source_fund_filter_for_all_four_statements(self):
        from django.forms.models import model_to_dict
        from .forms import ReportDefinitionForm

        for run in self.original_runs.values():
            definition = run.definition
            payload = model_to_dict(definition, fields=ReportDefinitionForm.Meta.fields)
            payload.update(filter_field="fund_code", filter_operator="exact", filter_value="GF")
            form = ReportDefinitionForm(payload, instance=definition, department=self.department, user=self.maker)
            self.assertTrue(form.is_valid(), form.errors)
            stored = form.save()
            self.assertEqual(stored.filters, {"fund_code__exact": "GF"})
            payload.update(filter_operator="contains")
            rejected = ReportDefinitionForm(payload, instance=stored, department=self.department, user=self.maker)
            self.assertFalse(rejected.is_valid())
            self.assertIn("filter_operator", rejected.errors)
