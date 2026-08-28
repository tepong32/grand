class FinanceDatabaseRouter:
    """Keep GRAND's standalone accounting ledger in its own database."""

    app_label = "accounting"
    database = "finance"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.app_label:
            return self.database
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.app_label:
            return self.database
        return None

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if self.app_label in labels:
            return labels == {self.app_label}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.app_label:
            return db == self.database
        if db == self.database:
            return False
        return None
