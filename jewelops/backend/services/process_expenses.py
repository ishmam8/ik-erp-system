from decimal import Decimal
from django.db import IntegrityError, transaction
from accounting_ledger.models import RST, PaymentMethod, RSTItem, Sales, Item, SaleItem, SalePayment, GoldPayment, ItemStatus, PaymentKind
from accounting_ledger.utils import parse_item_codes, parse_payment_methods, to_decimal
import logging

from api.accounting_ledger.serializers import ExpenseComposeSerializer
logger = logging.getLogger("ledger.sales")

def process_expenses_rows(user, rows, business_date):
    results = []
    errors = []
    serializer = None

    logger.info(
        "Create user_id=%s date=%s sales_count=%s expense_type=%s",
        getattr(user, "id", None),
        business_date,
        len(rows),
        [r.get("expense_type") for r in rows],
    )

    with transaction.atomic():
        for idx, row in enumerate(rows):
            cleaned_row = {
                'business_date': business_date,
                'expense_type': row.get('expense_type'),
                'description': row.get('description'),
                'amount': to_decimal(row.get('amount')),
                'payment_method': row.get('payment_method'),
            }
            serializer = ExpenseComposeSerializer(data={"row": cleaned_row})
            try: 
                serializer.is_valid(raise_exception=True)
                expense_instance = serializer.save()
                results.append({
                    "row": idx,
                    "sale_id": expense_instance.id,
                    "expense_type": expense_instance.expense_type
                })
                # logger.info(
                #     "Row Saved",
                #         "date": business_date,
                #         "row_index": idx,
                #         "invoice_number": sale_instance.invoice_number,
                #         "sale_id": sale_instance.id,
                # )
            except Exception as e:
                errors.append({"row": idx, "expense_type": row.get('expense_type'), "description": row.get('description'), errors: str(e)})
                logger.warning(
                    "Row Failed date=%s error=%s data=%s",
                    business_date,
                    str(e),
                    cleaned_row,
                )
        logger.info(
            "Submission Report date=%s rows_attempted=%s rows_saved=%s rows_failed=%s saved_expenses=%s failed_expenses=%s",
            business_date,
            len(rows),
            len(results),
            len(errors),
            [r["expense_type"] for r in results],
            [e["expense_type"] for e in errors],
        )
    return results, errors