# accounting_ledger/management/commands/import_artisan_g_history.py
import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now

from accounting_ledger.models import Artisan, ArtisanOrders

logger = logging.getLogger(__name__)
DEC0 = Decimal("0.00")


def norm_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def parse_decimal(s: str) -> Decimal:
    try:
        return Decimal(str(s).strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid decimal: {s!r}")


def parse_date(s: str) -> Optional[datetime.date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date {s!r}, expected YYYY-MM-DD") from e


@dataclass(frozen=True)
class Row:
    artisan_name: str
    date: Optional[datetime.date]
    tx_type: str
    description: str
    gold_g: Decimal
    running_balance: Optional[Decimal]
    row_index: int


def make_invoice_hash(*, file_basename: str, row: Row) -> str:
    payload = "|".join(
        [
            "CSVHASH",
            norm_text(file_basename),
            norm_text(row.artisan_name),
            row.date.isoformat() if row.date else "NO_DATE",
            norm_text(row.tx_type),
            f"{row.gold_g:.3f}",
            norm_text(row.description),
            str(row.row_index),
        ]
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"CSVHASH:{digest[:20]}"


def map_tx_type(csv_tx: str) -> Optional[str]:
    t = norm_text(csv_tx)
    if t == "pay":
        return ArtisanOrders.ArtisanTransactionType.RAW_G
    if t == "receive":
        return ArtisanOrders.ArtisanTransactionType.DELIVER_J
    if t in {"", "last audit", "audit"}:
        return None
    raise ValueError(f"Unknown Transaction Type: {csv_tx!r} (expected Pay/Receive)")


class Command(BaseCommand):
    help = "Load artisan gold ledger CSVs into ArtisanOrders (incremental, baseline-safe)."

    def _log_skip(self, filename: str, artisan: Artisan, r: Row, reason: str) -> None:
        msg = (
            f"[SKIP] file={filename} artisan={artisan.name} row={r.row_index} "
            f"date={r.date} tx={r.tx_type!r} gold_g={r.gold_g} rb={r.running_balance} "
            f"desc={r.description!r} reason={reason}"
        )
        self.stdout.write(self.style.WARNING(msg))
        logger.info(msg)

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-dir",
            type=str,
            required=False,
            help="Folder containing artisan CSVs (default: <BASE_DIR>/ETL_outputs/artisans).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run import but roll back all DB changes.",
        )
        parser.add_argument(
            "--validate-running-balance",
            action="store_true",
            help="Validate Running Balance column (only for Pay/Receive rows).",
        )
        parser.add_argument(
            "--errors-json",
            type=str,
            required=False,
            help="Optional path to write error details as JSON.",
        )

    def handle(self, *args, **options):
        csv_dir_str = options.get("csv_dir") \
            or str(Path(__file__).resolve().parent.parent.parent.parent.parent / "ETL_outputs" / "artisans/gold_history")
        
        csv_dir = Path(csv_dir_str)

        if not csv_dir.exists() or not csv_dir.is_dir():
            raise CommandError(f"CSV folder not found: {csv_dir}")

        files = sorted([p for p in csv_dir.iterdir() if p.suffix.lower() == ".csv"])
        if not files:
            self.stdout.write(self.style.WARNING(f"No CSV files found in {csv_dir}"))
            return

        dry_run = bool(options.get("dry_run"))
        validate_rb = bool(options.get("validate_running_balance"))
        errors_json_path = options.get("errors_json")

        self.stdout.write(self.style.WARNING(f"Using CSV dir: {csv_dir}"))

        all_errors: list[dict] = []
        total_created = 0
        total_skipped = 0

        ctx = transaction.atomic() if dry_run else _noop_context()

        with ctx:
            for csv_path in files:
                self.stdout.write(f"\nProcessing: {csv_path.name}")

                try:
                    rows = self._read_csv(csv_path)
                    if validate_rb:
                        self._validate_running_balances(csv_path.name, rows)

                    created, skipped = self._import_file(csv_path.name, rows)
                    total_created += created
                    total_skipped += skipped

                    self.stdout.write(
                        self.style.SUCCESS(f"{csv_path.name}: created={created} skipped={skipped}")
                    )
                except Exception as e:
                    all_errors.append({"file": csv_path.name, "error": str(e)})
                    self.stdout.write(self.style.ERROR(f"{csv_path.name}: ERROR {e}"))
                    logger.exception("Import failed for %s", csv_path.name)

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run enabled, rolling back all changes"))
                raise transaction.TransactionManagementError(
                    "Dry run complete, transaction rolled back intentionally."
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("==== ARTISAN IMPORT SUMMARY ===="))
        self.stdout.write(f"Files:         {len(files)}")
        self.stdout.write(f"Rows created:  {total_created}")
        self.stdout.write(f"Rows skipped:  {total_skipped}")
        self.stdout.write(f"Errors:        {len(all_errors)}")

        if errors_json_path:
            p = Path(errors_json_path)
            p.write_text(json.dumps(all_errors, indent=2), encoding="utf-8")
            self.stdout.write(self.style.WARNING(f"Error details written to {p}"))

    def _read_csv(self, csv_path: Path) -> list[Row]:
        rows: list[Row] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {"Karigar", "Date", "Transaction Type", "Description", "Gold (g)", "Running Balance"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"CSV missing columns {missing} in file: {csv_path}")

            for i, r in enumerate(reader, start=2):
                artisan_name = (r.get("Karigar") or "").strip()
                if not artisan_name:
                    raise CommandError(f"Empty Karigar at line {i} in {csv_path.name}")

                date = parse_date(r.get("Date"))
                tx_type = (r.get("Transaction Type") or "").strip()
                desc = (r.get("Description") or "").strip()
                gold_g = parse_decimal(r.get("Gold (g)"))

                rb_raw = (r.get("Running Balance") or "").strip()
                running_balance = parse_decimal(rb_raw) if rb_raw else None

                rows.append(
                    Row(
                        artisan_name=artisan_name,
                        date=date,
                        tx_type=tx_type,
                        description=desc,
                        gold_g=gold_g,
                        running_balance=running_balance,
                        row_index=i - 1,
                    )
                )
        return rows

    # def _validate_running_balances(self, filename: str, rows: list[Row]) -> None:
        # by_artisan: dict[str, list[Row]] = {}
        # for r in rows:
        #     by_artisan.setdefault(r.artisan_name.strip(), []).append(r)

        # for artisan_name, items in by_artisan.items():
        #     artisan, _ = Artisan.objects.get_or_create(
        #         name=artisan_name.strip(),
        #         defaults={
        #             "last_audit_date": now().date(),
        #             "last_transaction_date": now().date(),
        #             "jewellery_balance_g": Decimal("0"),
        #         },
        #     )

        #     bal = artisan.jewellery_balance_g or Decimal("0")

        #     # sort for validation stability
        #     items_sorted = sorted(items, key=lambda x: (x.date or now().date(), x.row_index))

        #     for r in items_sorted:
        #         tx = map_tx_type(r.tx_type)
        #         if tx is None:
        #             continue

        #         if tx == ArtisanOrders.ArtisanTransactionType.RAW_G:
        #             bal += r.gold_g
        #         else:
        #             bal -= r.gold_g

        #         if r.running_balance is not None:
        #             if (bal - r.running_balance).copy_abs() > Decimal("0.02"):
        #                 raise CommandError(
        #                     f"{filename}: Running Balance mismatch for {r.artisan_name} at row {r.row_index}. "
        #                     f"start_db={artisan.jewellery_balance_g} computed={bal} csv={r.running_balance}"
        #                 )

    def _import_file(self, filename: str, rows: list[Row]) -> tuple[int, int]:
        file_basename = Path(filename).name

        by_artisan: dict[str, list[Row]] = {}
        for r in rows:
            by_artisan.setdefault(r.artisan_name.strip(), []).append(r)

        created = 0
        skipped = 0

        for artisan_name, items in by_artisan.items():
            artisan, _ = Artisan.objects.get_or_create(
                name=artisan_name.strip(),
                defaults={
                    "last_audit_date": now().date(),
                    "last_transaction_date": now().date(),
                },
            )

            # sort so last_transaction_date update is correct
            items = sorted(items, key=lambda x: (x.date or now().date(), x.row_index))

            invoice_numbers = [make_invoice_hash(file_basename=file_basename, row=r) for r in items]
            existing = set(
                ArtisanOrders.objects.filter(
                    artisan=artisan, invoice_number__in=invoice_numbers
                ).values_list("invoice_number", flat=True)
            )

            new_orders: list[ArtisanOrders] = []
            delta = Decimal("0")
            new_dates: list[datetime.date] = []

            for r, inv in zip(items, invoice_numbers):
                if inv in existing:
                    skipped += 1
                    self._log_skip(filename, artisan, r, f"duplicate invoice_number {inv}")
                    continue

                tx = map_tx_type(r.tx_type)
                if tx is None:
                    skipped += 1
                    self._log_skip(filename, artisan, r, "baseline/audit row")
                    continue

                if r.date is None:
                    raise CommandError(f"{filename}: missing Date for {r.artisan_name} at row {r.row_index}")

                if r.date <= artisan.last_transaction_date:
                    skipped += 1
                    self._log_skip(filename, artisan, r, "missing date")
                    continue

                if tx == ArtisanOrders.ArtisanTransactionType.RAW_G:
                    delta += r.gold_g
                else:
                    delta -= r.gold_g

                new_orders.append(
                    ArtisanOrders(
                        artisan=artisan,
                        date=r.date,
                        total_weight=r.gold_g,
                        transaction_type=tx,
                        note=r.description,
                        invoice_number=inv,
                    )
                )
                new_dates.append(r.date)

            if new_orders:
                ArtisanOrders.objects.bulk_create(new_orders, batch_size=1000)
                created += len(new_orders)

                Artisan.objects.filter(id=artisan.id).update(
                    # jewellery_balance_g=F("jewellery_balance_g") + delta,
                    last_transaction_date=max(new_dates),
                )

        return created, skipped


class _noop_context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
