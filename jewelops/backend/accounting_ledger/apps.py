from django.apps import AppConfig

class AccountingLedgerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounting_ledger'

    def ready(self):
        import accounting_ledger.signals