from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .models import BudgetOfficeForm


class OfficeFormRetentionTests(SimpleTestCase):
    def test_all_retained_states_reject_instance_deletion_before_database_access(self):
        for state in (BudgetOfficeForm.PREPARED, BudgetOfficeForm.ISSUED, BudgetOfficeForm.RETURNED):
            item = BudgetOfficeForm(pk=42, status=state)
            with self.subTest(state=state), patch('django.db.models.Model.delete') as delete:
                with self.assertRaisesMessage(ValidationError, 'Retain office-form'):
                    item.delete(using='finance')
                delete.assert_not_called()
