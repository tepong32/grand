from django.db import transaction
from django.test import TransactionTestCase

from departments.models import Department

from .issuance_boundaries import lock_foundation_issuance_boundary
from .models import FinanceFoundationIssuanceBoundary


class FinanceFoundationIssuanceBoundaryTests(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.department = Department.objects.create(
            name="Synthetic Accounting Boundary Office",
            slug="synthetic-accounting-boundary",
        )

    def test_lock_requires_a_default_database_transaction(self):
        with self.assertRaisesMessage(RuntimeError, "inside a default-database transaction"):
            lock_foundation_issuance_boundary(
                department_id=self.department.pk,
                fiscal_year=2027,
            )

    def test_lock_record_is_unique_and_reused_for_the_same_scope(self):
        with transaction.atomic(using="default"):
            first = lock_foundation_issuance_boundary(
                department_id=self.department.pk,
                fiscal_year=2027,
            )
            second = lock_foundation_issuance_boundary(
                department_id=self.department.pk,
                fiscal_year=2027,
            )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(FinanceFoundationIssuanceBoundary.objects.filter(
            department=self.department,
            fiscal_year=2027,
        ).count(), 1)
