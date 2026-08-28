class FinanceDatabaseRouter:
    """Keep GRAND's standalone Accounting and Budget authority data in its Finance database."""

    app_labels = {"accounting", "budget"}
    database = "finance"

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.app_labels:
            return self.database
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.app_labels:
            return self.database
        return None

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if labels & self.app_labels:
            return labels <= self.app_labels
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.app_labels:
            return db == self.database
        if db == self.database:
            return False
        return None
