



from pathlib import Path
from pprint import pprint
import pandas as pd
import pytest

from accounting_ledger.models import RST, Expense, Item, GoldPayment, Order, RSTItem, SaleItem, SalePayment, Sales
from accounting_ledger.utils import parse_order_date, safe_int
from services.process_sales import process_sales_rows
from services.process_expenses import process_expenses_rows

def _print_db_snapshot():
    print("\n=== DB SNAPSHOT ===")
    items = list(
        Item.objects.order_by("code").values(
            "code", "purity", "description", "status","created_at", "updated_at",
        )
    )
    sales = list(
        Sales.objects.order_by("id").values(
            "id", "business_date", "invoice_number", "customer_name",
            "sold_by", "item_count", "total_weight", "total_sale_price",
        )
    )
    sale_items = list(
        SaleItem.objects.order_by("sale_id", "id").values(
            "id", "sale_id", "item__code", "description", "purity_price",
        )
    )
    payments = list(
        SalePayment.objects.order_by("sale_id", "id").values(
            "id", "sale_id", "method", "amount", "due_amount", "due_by", "kind", "description",
        )
    )
    golds = list(
        GoldPayment.objects.order_by("payment__sale_id", "id").values(
            "id", "payment_id", "payment__sale_id", "weight", "purity",
        )
    )
    rst=list(
        RST.objects.order_by("id").values(
          "id","sale_id","rst_adv",  
        )
    )
    rst_items=list(
        RSTItem.objects.order_by("rst_id").values(
          "rst_id","item", 
        )
    )
    order=list(
        Order.objects.order_by("sale_id").values(
          "sale_id","assigned_to","is_completed","delivery_date",
          "completed_at","item_description" 
        )
    )
    print("\n-- Items --")
    pprint(items)
    print("\n-- Sales --")
    pprint(sales)
    print("\n-- SaleItems --")
    pprint(sale_items)
    print("\n-- SalePayments --")
    pprint(payments)
    print("\n-- GoldPayments --")
    pprint(golds)
    print("\n-- RSTPayments --")
    pprint(rst)
    print("\n-- RSTItemPayments --")
    pprint(rst_items)
    print("\n-- Order --")
    pprint(order)
    
    expenses = list(
        Expense.objects.order_by("business_date").values()
    )
    pprint(expenses)



@pytest.fixture
def expenses_df() -> pd.DataFrame:
    # Path: tests/unit/data/expenses_sample.csv
    csv_path = Path(__file__).resolve().parent.parent.parent.parent / "ETL_outputs" / "expenses.csv"
    df = pd.read_csv(csv_path)

    # Normalize date column
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df



@pytest.fixture
def sales_df() -> pd.DataFrame:
    # 🔁 Adjust this path to where your CSV actually lives
    csv_path = (
        Path(__file__)
        .resolve()
        .parent.parent.parent.parent
        / "ETL_outputs"
        / "sales.csv"
    )
    df = pd.read_csv(csv_path, keep_default_na=False, na_values=[])

    # Normalize Date column
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df


@pytest.mark.django_db
def test_sales_load_processing(sales_df):

    # Confirm once; these are DataFrame columns, not per-row values
    # print(sales_df.columns.tolist())
    assert "Invoice No" in sales_df.columns
    assert "Invoice No.1" in sales_df.columns

    for business_date, day_df in sales_df.groupby("Date"):
        sales_rows = []
        order_rows = []

        # 1️⃣ Build a dict of order meta rows from the right-hand columns
        order_meta_by_invoice = {}
        for _, row in day_df.iterrows():
            raw_order_inv = row.get("Invoice No.1")
            order_inv = safe_int(raw_order_inv)
            if not order_inv:
                continue  # no order meta on this row

            order_meta_by_invoice[str(order_inv)] = {
                "invoice_number": order_inv,
                "customer_name": row.get("Customer Name.1") or "",
                "item_name": row.get("Item Description.1") or "",
                "artisan": row.get("Artisan Assigned") or "",
                "estimated_order_delivery_date": parse_order_date(row.get("Date to Deliver")),
                # I assume 'Ready for Handover' is the completion date.
                "order_completed_date": parse_order_date(row.get("Ready for Handover")),
            }

        # convert dict to list for process_sales_rows
        for inv_str, meta in order_meta_by_invoice.items():
            order_rows.append(meta)

        # 2️⃣ Build sales_rows from the left-hand columns
        for _, row in day_df.iterrows():

            sale_price_raw = str(row.get("Sale Price (BDT)") or "").strip().upper()
            customer_name_raw = str(row.get("Customer Name") or "").strip().upper()
            payment_method_raw = str(row.get("Payment Method") or "").strip().upper()

            rst_order = "SALE"
            if sale_price_raw == "RST" or "RST" in payment_method_raw:
                rst_order = "RST"
            elif sale_price_raw == "ORDER" or customer_name_raw == "ORDER":
                rst_order = "ORDER"

            # detect RST / ORDER rows
            sale_price = row.get("Sale Price (BDT)")
            customer_name = str(row.get("Customer Name") or "").strip()

            sales_row = {
                "invoice_number": row["Invoice No"],
                "customer_name": customer_name,
                "item_code": row.get("Item Code"),
                "item": row.get("Item Description"),
                "quantity": row.get("Item No."),
                "gold_weight": row.get("Gold Weight (g)"),
                "kdm_vori": row.get("KDM/Vhori"),
                "sale_price": sale_price,
                "cash_card_payment": row.get("Cash/Card Pay (BDT)"),
                "gold_payment": row.get("Gold Weight/Value"),
                "payment_type": row.get("Payment Method"),
                "sold_by": row.get("Sold By"),
                "customer_due": row.get("Due Amount"),
                "due_by": row.get("Due By"),

                "rst_order": rst_order,                   # 'RST', 'ORDER', or None
                "rst_payment": 0,                   # placeholder: update later if you track it
                "rst_advanced": row.get("RST Value"),
                "rst_status": "",                   # placeholder
            }

            # ❗ You likely want to skip pure "Due Receive" rows, etc.
            # e.g., if customer_name == 'Due Receive' -> continue
            # but that depends on your business rules.

            sales_rows.append(sales_row)

        # 3️⃣ Call your processing function
        results, errors = process_sales_rows(
            rows=sales_rows,
            order_rows=order_rows,
            business_date=business_date,
            user=None,
        )

        # Assertions per date
        assert not errors
        assert len(results) == len(sales_rows)

    _print_db_snapshot()



def test_expenses_load_processing(expenses_df):
    # For each business date, run the ETL separately
    for business_date, day_df in expenses_df.groupby("Date"):
        rows = [
            {
                "expense_type": row["Expense Type"],
                "description": row["Description"],
                "amount": row["Amount (BDT)"],
                "payment_method": row["Paid By"],
            }
            for _, row in day_df.iterrows()
        ]

        results, errors = process_expenses_rows(
            user=None,
            rows=rows,
            business_date=business_date,
        )

        # Adjust these based on your real behaviour
        assert errors == []                 # or assert not errors
        assert len(results) == len(rows)
    _print_db_snapshot() 
    # print("\n-- Expenses --")
    # pprint(Expense.objects.all().values())