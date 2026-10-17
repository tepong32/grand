from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from accounting.models import Fund, LedgerAccount
from inventory.models import Asset, PropertyDetermination
from inventory_finance.models import PropertyFinanceLink as Link
from . import test_grand_property_links as fixtures


class PropertyLinkMigrationTests(TransactionTestCase):
    databases = {"default", "finance"}

    def test_populated_upgrade_preserves_property_finance_and_grants(self):
        fixtures.PropertyLinkTests.setUpTestData.__func__(type(self))
        fixtures.PropertyLinkTests.setUp(self)
        assets = list(Asset.objects.order_by("pk").values())
        properties = list(PropertyDetermination.objects.order_by("pk").values())
        funds = list(Fund.objects.order_by("pk").values())
        accounts = list(LedgerAccount.objects.order_by("pk").values())
        grants = list(self.clerk.user_permissions.order_by("pk").values_list("pk", flat=True))
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("inventory_finance", "0004_receiptjournalmapping_receiptjournalmappingevent_and_more")])
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(list(Asset.objects.order_by("pk").values()), assets)
            self.assertEqual(list(PropertyDetermination.objects.order_by("pk").values()), properties)
            self.assertEqual(list(Fund.objects.order_by("pk").values()), funds)
            self.assertEqual(list(LedgerAccount.objects.order_by("pk").values()), accounts)
            self.assertEqual(list(self.clerk.user_permissions.order_by("pk").values_list("pk", flat=True)), grants)
            self.assertFalse(Link.objects.exists())
            row = fixtures.PropertyLinkTests.request(self)
            duplicate = {f.attname: getattr(row, f.attname) for f in Link._meta.concrete_fields
                if not f.primary_key and not f.generated and f.attname != "public_id"}
            with self.assertRaises(IntegrityError), transaction.atomic():
                Link.objects.create(**duplicate)
            with self.assertRaises(IntegrityError), transaction.atomic():
                Link.objects.filter(pk=row.pk).update(status="approved", proposed_by=self.clerk,
                    decided_by=self.clerk, decided_at=timezone.now())
        finally:
            MigrationExecutor(connection).migrate(leaves)
