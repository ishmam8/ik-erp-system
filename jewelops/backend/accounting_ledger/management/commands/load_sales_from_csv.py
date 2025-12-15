# ledger/management/commands/load_sales_from_csv.py
import json
import logging
import os
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting_ledger.models import Sales  # adjust app/model import if needed
from services.process_sales import process_sales_rows  # your function
from etl.load import iter_sales_batches


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load sales + orders from the ETL sales CSV into the local database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            type=str,
            required=False,
            help="Path to the sales_<>.csv file (default: ./ETL_outputs/sales_<>.csv)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the ETL but roll back all DB changes (for safety).",
        )
        parser.add_argument(
            "--errors-json",
            type=str,
            required=False,
            help="Optional path to write error details as JSON.",
        )

    def handle(self, *args, **options):
        # 🔁 CSV PATH PLACEHOLDER: change default if your folder name is different
        csv_path_str = options.get("csv_path") or str(
            Path(__file__).resolve().parent.parent.parent.parent.parent / "ETL_outputs" / f"sales_{os.getenv('ETL_WORKSHEET_NAME').lower()}.csv"
        )
        csv_path = Path(csv_path_str)

        if not csv_path.exists():
            raise CommandError(f"CSV not found at {csv_path}")

        self.stdout.write(self.style.WARNING(f"Using CSV: {csv_path}"))

        # Read CSV exactly like the fixture
        df = pd.read_csv(csv_path, keep_default_na=False, na_values=[])
        df["Date"] = pd.to_datetime(df["Date"]).dt.date

        dry_run = options.get("dry_run", False)
        errors_json_path = options.get("errors_json")

        all_errors = []
        total_saved = 0
        total_attempted = 0

        # Wrap whole run in a single transaction if dry_run
        ctx = transaction.atomic() if dry_run else _noop_context()

        with ctx:
            for business_date, sales_rows, order_rows in iter_sales_batches(df):
                self.stdout.write(f"Processing date {business_date} ...")

                results, errors = process_sales_rows(
                    rows=sales_rows,
                    order_rows=order_rows,
                    business_date=business_date,
                    user=None,
                )

                total_attempted += len(sales_rows)
                total_saved += len(results)
                all_errors.extend(
                    {
                        "business_date": str(business_date),
                        "row_index": e["row"],
                        "invoice_number": e["invoice_number"],
                        "errors": e["errors"],
                    }
                    for e in errors
                )

                # Per-day logging
                logger.info(
                    "ETL date=%s rows_attempted=%s rows_saved=%s rows_failed=%s",
                    business_date,
                    len(sales_rows),
                    len(results),
                    len(errors),
                )

                if errors:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠ Errors on {business_date}: {len(errors)} rows failed"
                        )
                    )

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run enabled – rolling back all changes"))
                raise transaction.TransactionManagementError(
                    "Dry run complete – transaction rolled back intentionally."
                )

        # Global summary
        db_count = Sales.objects.count()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("==== ETL SUMMARY ===="))
        self.stdout.write(f"Rows attempted: {total_attempted}")
        self.stdout.write(f"Rows saved:     {total_saved}")
        self.stdout.write(f"Errors:         {len(all_errors)}")
        self.stdout.write(f"Sales in DB:    {db_count}")

        if all_errors:
            logger.warning("ETL finished with %s errors", len(all_errors))

        # Optional: dump errors to JSON file
        if errors_json_path:
            errors_path = Path(errors_json_path)
            errors_path.write_text(json.dumps(all_errors, indent=2), encoding="utf-8")
            self.stdout.write(self.style.WARNING(f"Error details written to {errors_path}"))


class _noop_context:
    """Context manager that does nothing, used when not in dry_run."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
