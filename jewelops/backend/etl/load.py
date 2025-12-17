# ledger/etl/load.py
from datetime import datetime
from typing import Dict, List, Tuple, Any, Iterable

import math
import pandas as pd


def safe_int(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s or not s.isdigit():
        return None
    return int(s)


def parse_order_date(value):
    """
    Same tolerance you used in tests:
    DD/MM/YYYY -> date; anything else (RST, Yes/No, blank) -> None.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    s = str(value).strip()
    if not s:
        return None

    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None


def iter_sales_batches(sales_df: pd.DataFrame) -> Iterable[Tuple[Any, List[Dict], List[Dict]]]:
    """
    Yield (business_date, sales_rows, order_rows) for each Date group.
    This is basically your test logic, refactored.
    """

    assert "Invoice No" in sales_df.columns
    assert "Invoice No.1" in sales_df.columns

    for business_date, day_df in sales_df.groupby("Date"):
        sales_rows: List[Dict] = []
        order_rows: List[Dict] = []

        # 1️⃣ Build order meta (right-hand block)
        order_meta_by_invoice: Dict[str, Dict] = {}
        for _, row in day_df.iterrows():
            raw_order_inv = row.get("Invoice No.1")
            order_inv = safe_int(raw_order_inv)
            if not order_inv:
                continue

            order_meta_by_invoice[str(order_inv)] = {
                "invoice_number": order_inv,
                "customer_name": row.get("Customer Name.1") or "",
                "item_name": row.get("Item Description.1") or "",
                "artisan": row.get("Artisan Assigned") or "",
                "estimated_order_delivery_date": parse_order_date(row.get("Date to Deliver")),
                "order_completed_date": parse_order_date(row.get("Ready for Handover")),
            }

        order_rows.extend(order_meta_by_invoice.values())

        # 2️⃣ Build sales_rows from left-hand block
        for _, row in day_df.iterrows():
            raw_inv = row.get("Invoice No")
            inv_num = safe_int(raw_inv)

            sale_price_raw = str(row.get("Sale Price (BDT)") or "").strip().upper()
            rst_adv_raw = str(row.get("RST Value") or "").strip().upper()
            customer_name_raw = str(row.get("Customer Name") or "").strip()
            customer_name_upper = customer_name_raw.upper()
            payment_method_raw = str(row.get("Payment Method") or "").strip().upper()
            item_desc_raw = str(row.get("Item Description") or "").strip().lower()

            tag = None
            if sale_price_raw == "RST" or rst_adv_raw or "RST" in payment_method_raw:
                tag = "RST"
            if sale_price_raw == "ORDER" or customer_name_upper == "ORDER":
                # Don't treat pure 'Advance' rows as ORDER
                if item_desc_raw != "advance":
                    tag = "ORDER"

            sales_row = {
                "invoice_number": inv_num,
                "customer_name": customer_name_raw,
                "item_code": row.get("Item Code"),
                "item": row.get("Item Description"),
                "quantity": row.get("Item No."),
                "gold_weight": row.get("Gold Weight (g)"),
                "kdm_vori": row.get("KDM/Vhori"),
                "sale_price": row.get("Sale Price (BDT)"),
                "cash_card_payment": row.get("Cash/Card Pay (BDT)"),
                "gold_payment": row.get("Gold Weight/Value"),
                "payment_type": row.get("Payment Method"),
                "sold_by": row.get("Sold By"),
                "customer_due": row.get("Due Amount"),
                "due_by": row.get("Due By"),
                "rst_order": tag or "",
                "rst_payment": 0,
                "rst_advanced": row.get("RST Value"),
                "rst_status": "",
            }

            sales_rows.append(sales_row)

        yield business_date, sales_rows, order_rows
